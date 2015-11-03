#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Classes Managing misfits
"""
import sys
import os.path
#
import numpy as np
import scipy.signal
#
import json
#
from obspy import UTCDateTime, read
from obspy.core.util.geodetics import gps2DistAzimuth, kilometer2degrees
from obspy.taup import TauPyModel
from obspy.imaging.beachball import Beach
#
import pyproj
#
from lanczos_interp1 import lanczos_interp1
#
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap


# utilities
def _taper_(npts, taper_type="cosine", taper_percentage=0.05):
    """taper function of npts points
        taper_percentage: decimal percentage at one end (5%)
    """
    if not 0.0 < taper_percentage <= 0.5:
        print "[ERROR] taper_percentage must between 0.0 and 0.5"
        sys.exit()

    taper = np.ones(npts)

    x = np.linspace(0, 1.0, npts)
    il = int((npts-1)*taper_percentage)
    ir = int(npts*(1.0-taper_percentage)+1)
    if taper_type == "cosine":
        taper[0:il+1] = 0.5 * (1.0 - np.cos(
            np.pi*x[0:il+1]/taper_percentage) )
        taper[ir:] = 0.5 * (1.0 - np.cos(
            np.pi*(1.0 - x[ir:])/taper_percentage) )
    else:
        print "[ERROR] %s unrecognized taper type" % (taper_type)
        sys.exit()

    return taper


#
class Misfit(object):
    """Class managing all misfit windows

    data structure:

    Misfit: {
    |   'iteration': {iter, ...}, 
    |   'events': {
    |   *   <event_id>: {
    |   |   |   'gcmt': {lat,lon,depth, ...}, 
    |   |   |   'relocate1d': {
    |   |   |   |   'phase_list': ['p', 'P',...],
    |   |   |   |   'filter': {SNR, cc_0, cc_max,...}, 
    |   |   |   |   'latitude': , 'longitude': ...
    |   |   |   |   'residual_linear': 
    |   |   |   'stations': {
    |   |   |   *   <station_id(net.sta.loc)>: {
    |   |   |   |   |   'meta': {lat,lon,ele,...,channels:{code,az,dip,...} },
    |   |   |   |   |   'window_param': {
    |   |   |   |   |   |   'filter': {type, freqlim(list), ncorners},
    |   |   |   |   |   |   'taper': {type, percentage} },
    |   |   |   |   |   'noise_window': {starttime, endtime}, # pre-event time window
    |   |   |   |   |   'stat': {code, msg}, # code<0: problematic, code=0: OK 
    |   |   |   |   |   'windows': {
    |   |   |   |   |   *   <window_id(cmp.pha)>: {
    |   |   |   |   |   |   |   component, azimuth, dip,
    |   |   |   |   |   |   |   starttime, endtime, weight
    |   |   |   |   |   |   |   'phase': {name, ttime, takeoff_angle, ray_param},
    |   |   |   |   |   |   |   'quality': {A_obs, A_noise, SNR},
    |   |   |   |   |   |   |   'misfit': {cc_0, cc_max, cc_time_shift,
    |   |   |   |   |   |   |              ar_0, ar_max },
    |   |   |   |   |   |   |   'stat': {code, msg} }, #code<0: problematic, code=0: not measured, code=1: measured
    |   |   |   |   |   *   <window_id>: { },
    |   |   |   |   |   |   ...
    |   |   |   *   <station_id>: { ... },
    |   |   |   |   ...
    |   *   <event_id>: { ... },
    |   |   ...
    """

    def __init__(self):
        """Misfit dict
        """
        self.data = {'events':{}}


    def save(self, filename='misfit.json'):
        """Save data
        """
        with open(filename, 'w') as fp:
            json.dump(self.data, fp, indent=2)
            

    def load(self, filename='misfit.json'):
        """Load data
        """
        with open(filename, 'r') as fp:
            self.data = json.load(fp)


    def setup_event_from_CMTSOLUTION(self, cmt_file, update=False):
        """cmt_file (str): CMTSOLUTION format file
        """
        with open(cmt_file, 'r') as f:
            cmt = [x.split() for x in f.readlines() if not(x.startswith('#'))]
        # PDE
        year  = cmt[0][1]
        month  = cmt[0][2]
        day = cmt[0][3]
        hour  = cmt[0][4]
        minute = cmt[0][5]
        second = cmt[0][6]
        # CMT results
        event_id = cmt[1][2]
        time_shift = float(cmt[2][2])
        half_duration = float(cmt[3][2])
        lat = float(cmt[4][1])
        lon = float(cmt[5][1])
        depth = float(cmt[6][1])
        # centroid time 
        isotime = '{:s}-{:s}-{:s}T{:s}:{:s}:{:s}Z'.format(
                year, month, day, hour, minute, second)
        centroid_time = UTCDateTime(isotime) + time_shift
        # moment tensor 
        # basis: (r,theta,phi) corresponds to (up,south,east)
        Mrr = float(cmt[7][1])
        Mtt = float(cmt[8][1])
        Mpp = float(cmt[9][1])
        Mrt = float(cmt[10][1])
        Mrp = float(cmt[11][1])
        Mtp = float(cmt[12][1])
        M = [[Mrr, Mrt, Mrp], [Mrt, Mtt, Mtp], [Mrp, Mtp, Mpp]]

        # add event
        events = self.data['events']
        gcmt = {'centroid_time':str(centroid_time), 
                'half_duration':half_duration,
                'latitude':lat, 'longitude':lon, 'depth':depth, 
                'moment_tensor':M}
        if event_id not in events:
            events[event_id] = {
                    'gcmt': gcmt,
                    'stations': {},
                    'stat': {'code': 0, 'msg': ""}}
        elif update:
            events[event_id]['gcmt'].update(gcmt)
            events[event_id]['stat']['msg'] = "updated"
            print "[WARNING] %s: update event info" % (event_id)
        else:
            print "[WARNING] %s: already exists, skip." % (event_id)


    def setup_stations_from_metafile(self, station_file,
            event_id_list=None, band_code=None, three_channels=True, 
            update=False):
        """ station_file (str): FDSN-station text format file at channel level
            event_id_list (list): list of event ID's to which stations are added [default: None]
            band_code (str): instrument/band code [default: None]
            three_channels (bool): check for completeness of 3 channels [default: False]

            Note: only use stations which have the same lat/lon/ele/depth 
                in all the available channels.
        """
        # read station file
        with open(station_file, 'r') as f:
            lines = [x.replace('\n','').split('|')  \
                    for x in f.readlines() if not(x.startswith('#'))]
        
        # get all station metadata
        stations_all = {}
        for x in lines:
            net_sta_loc = (x[0], x[1], x[2])
            channel = {'code':        x[3],
                       'latitude':    float(x[4]),
                       'longitude':   float(x[5]),
                       'elevation':   float(x[6]),
                       'depth':       float(x[7]),
                       'azimuth':     float(x[8]),
                       'dip':         float(x[9]),
                       'starttime':   x[15],
                       'endtime':     x[16] }
            if net_sta_loc not in stations_all:
                stations_all[net_sta_loc] = []
            stations_all[net_sta_loc].append(channel)

        # empty/Null event_id_list defaults to all events
        events = self.data['events']
        if not event_id_list:
            event_id_list = [ x for x in events ]

        # add stations for each event
        for event_id in event_id_list:
            # check if event info is set 
            if event_id not in events:
                print "[WARNING] %s does not exist, SKIP" % (event_id)
                continue

            event = events[event_id]
            stations = event['stations']
            gcmt = event['gcmt']

            # station active time is set to centroid time
            active_time = UTCDateTime(gcmt['centroid_time'])

            for net_sta_loc in stations_all:
                # station_id: net.sta.loc
                station_id = '.'.join(net_sta_loc)

                # skip existing stations if not update
                if (station_id in stations) and (not update):
                    print "[WARNING] %s already exists, SKIP." \
                            % (station_id)
                    continue

                # select channels which are active at the specified time 
                channels = [ x for x in stations_all[net_sta_loc] 
                        if UTCDateTime(x['starttime']) < active_time and 
                        UTCDateTime(x['endtime']) > active_time ]
                # select band code
                if band_code:
                    n = len(band_code)
                    channels = [ x for x in channels 
                            if x['code'][0:n]==band_code ]
                # check same locations for all selected channels 
                lats = [ x['latitude'] for x in channels ] 
                lons = [ x['longitude'] for x in channels ] 
                eles = [ x['elevation'] for x in channels ] 
                deps = [ x['depth'] for x in channels ] 
                if lats.count(lats[0])!=len(lats) or \
                        lons.count(lons[0])!=len(lons) or \
                        eles.count(eles[0])!=len(eles) or \
                        deps.count(deps[0])!=len(deps):
                    print "[WARNING] %s: " \
                          "channels do NOT have the same coordinates, SKIP." \
                          % (station_id)
                    continue
                # check completeness for 3-components
                if three_channels:
                    if len(channels) != 3:
                        print '[WARNING] %s: not exactly 3 components found, '\
                              'SKIP.' % (station_id)
                        continue
                    # check channel orientations
                    Z_comp = [ (x['code'], x['azimuth'], x['dip'])
                            for x in channels if x['code'][2] == 'Z']
                    if len(Z_comp) != 1 or abs(Z_comp[0][2]) != 90.0: 
                        print '[WARNING] %s: problematic Z channel, SKIP' \
                                % (station_id)
                        print '          channel: ', H_comp
                        continue
                    H_comp = [ (x['code'], x['azimuth'], x['dip']) \
                            for x in channels if x['code'][2] != 'Z']
                    if len(H_comp) != 2 or \
                            abs(H_comp[0][2]) != 0.0 or \
                            abs(H_comp[1][2]) != 0.0 or \
                            abs(np.cos(np.deg2rad(
                                H_comp[0][1] - H_comp[1][1]))) > 0.1: 
                        print '[WARNING] %s: problematic horizontal channels, SKIP'\
                                % (station_id)
                        print '          channel: ', H_comp
                        continue

                # geodetic
                dist, az, baz = gps2DistAzimuth(gcmt['latitude'], gcmt['longitude'],
                        channels[0]['latitude'], channels[0]['longitude'])
                dist_in_deg = kilometer2degrees(dist/1000.0)

                # form station metadata 
                meta = {'latitude': channels[0]['latitude'], 
                        'longitude': channels[0]['longitude'],
                        'elevation': channels[0]['elevation'],
                        'depth': channels[0]['depth'],
                        'azimuth': az,
                        'back_azimuth': baz,
                        'dist_in_deg': dist_in_deg,
                        'channels': channels }

                # add station info
                if station_id not in stations:
                    stations[station_id] = {
                            'meta': meta,
                            'windows': {},
                            'stat': {'code': 0, 'msg': ""} }
                elif update:
                    stations[station_id]['meta'].update(meta)
                    stations[station_id]['stat']['msg'] = "updated"

            #end for net_sta_loc in stations_all:
        #end for event_id in event_id_list:


    def setup_windows(self,
            window_list=[('Z','p,P',[-30,50]), ('T','s,S',[-40,70])],
            noise_window=('ttp',[-150,-40]),
            filter_param=('bandpass', [0.015,0.1], 2),
            taper_param=('cosine', 0.1),
            event_id_list=None, station_id_list=None, update=False):
        """window_list: [ (component, phases, [begin, end]), ...]
        """
        # check event/station_id_list
        events = self.data['events']
        if not event_id_list:
            event_id_list = [ x for x in events ]
        if not station_id_list:
            loop_all_stations = True
        else:
            loop_all_stations = False

        # initiate taup
        taup_model = TauPyModel(model="iasp91")

        # noise window param
        noise_phases = noise_window[0].split(',')
        noise_begin = noise_window[1][0]
        noise_end = noise_window[1][1]

        # make window_param
        window_param = {
            'filter': {'type': filter_param[0],
                       'freqlim': filter_param[1],
                       'ncorners': filter_param[2]},
            'taper': {'type': taper_param[0],
                      'percentage': taper_param[1]} }

        # loop each event
        for event_id in event_id_list:
            if event_id not in events:
                print "[WARNING] %s does NOT exist. SKIP" \
                        % (event_id)
                continue

            event = events[event_id]
            gcmt = event['gcmt']
            centroid_time = UTCDateTime(gcmt['centroid_time'])
            stations = event['stations']
            if loop_all_stations:
                station_id_list = [ x for x in stations ]

            # loop each station
            for station_id in station_id_list:
                if station_id not in stations:
                    print "[WARNING] %s:%s does NOT exist. SKIP" \
                            % (event_id, station_id)
                    continue

                station = stations[station_id]
                meta = station['meta']
                baz = meta['back_azimuth']
                dist_in_deg = meta['dist_in_deg']

                # setup window_param
                if 'window_param' not in station:
                    station['window_param'] = window_param
                elif update:
                    station['window_param'].update(window_param)

                # make noise window
                arrivals = taup_model.get_travel_times(
                        source_depth_in_km=gcmt['depth'],
                        distance_in_degree=dist_in_deg,
                        phase_list=noise_phases)
                if arrivals:
                    arr = arrivals[0]
                    noise_starttime = str(centroid_time + arr.time + noise_begin)
                    noise_endtime = str(centroid_time + arr.time + noise_end)
                else:
                    print "[WARNNING] %s:%s:%s phase(s) not found, skip." \
                            % (event_id, station_id, noise_window[0])
                    continue
                # setup noise window
                noise_window = { 'starttime': noise_starttime,
                        'endtime': noise_endtime }
                if 'noise_window' not in station:
                    station['noise_window'] = noise_window
                elif update:
                    station['noise_window'].update(noise_window)

                # loop each window
                windows = station['windows']
                for win in window_list:
                    comp = win[0]
                    phase = win[1]
                    signal_begin = float(win[2][0])
                    signal_end = float(win[2][1])
                    window_id = "%s.%s" % (comp, phase)
                    if (window_id in windows) and (not update):
                        print "[WARNING] %s:%s:%s already exists, skip" \
                                % (event_id, station_id, window_id)
                        continue

                    if comp == 'Z': # vertcal component
                        cmpaz = 0.0 
                        cmpdip = -90.0
                    elif comp == 'R': # radial component
                        cmpaz = (baz + 180.0)%360.0
                        cmpdip = 0.0
                    elif comp == 'T': # tangential component
                        cmpaz = (baz + 90.0)%360.0
                        cmpdip = 0.0
                    elif comp == 'H': # horizontal vector
                        cmpaz = float('nan')
                        cmpdip = float('nan')
                    elif comp == 'F': # full vector
                        cmpaz = float('nan')
                        cmpdip = float('nan')
                    else:
                        print "[WARNING] %s: unrecognized component, SKIP." \
                                % (comp)
                        continue
            
                    # phase arrivals predicted from reference Earth model
                    arrivals = taup_model.get_travel_times(
                            source_depth_in_km=gcmt['depth'],
                            distance_in_degree=dist_in_deg,
                            phase_list=phase.split(','))
                    if not arrivals:
                        print "[WARNING] %s:%s:%s phase not found, skip " \
                                % (event_id, station_id, phase)
                        continue

                    # add/update window
                    # only use first arrival of smallest traveltime
                    arr = arrivals[0]
                    signal_starttime = str(centroid_time + arr.time + signal_begin)
                    signal_endtime = str(centroid_time + arr.time + signal_end)
                    window = {
                        'component': comp,
                        'azimuth': cmpaz,
                        'dip': cmpdip,
                        'starttime': signal_starttime,
                        'endtime': signal_endtime,
                        'phase': {'name': arr.name, 'ttime': arr.time,
                                  'takeoff_angle': arr.takeoff_angle,
                                  'ray_param': arr.ray_param}, 
                        'quality': {},
                        'misfit': {},
                        'stat': {'code': 0, 'msg': ""} }
                    if window_id not in windows:
                        windows[window_id] = window
                    elif update:
                        windows[window_id].update(window)
                        windows[window_id]['stat']['msg'] = "updated"

                #end for winpar in winpar_list:
            #end for station_id in station_id_list:
        #end for event_id in event_id_list:


    def measure_windows_for_one_event(self, event_id, station_id_list=None,
            obs_dir='obs', syn_dir='syn', syn_band_code='MX', 
            syn_suffix='.sem.sac', adj_dir='adj', cc_delta=0.01, 
            output_adj=False, update=False):
        """measure misfit on time windoes for one event
            cc_delta: sampling interval for cross-correlation between obs and syn.
        """
        syn_orientation_codes = ['E', 'N', 'Z']
        # check inputs
        events = self.data['events']
        if event_id not in events:
            print "[WARNING] %s does NOT exist. Exit" \
                    % (event_id)
            sys.exit()

        event = events[event_id]
        stations = event['stations']
        if not station_id_list:
            station_id_list = [ x for x in stations ]

        # loop each station
        for station_id in station_id_list:
            if station_id not in stations:
                print "[WARNING] %s:%s does NOT exist. SKIP" \
                        % (event_id, station_id)
                continue

            station = stations[station_id]
            windows = station['windows']

            # get file paths of obs, syn seismograms
            meta = station['meta']
            channels = meta['channels']
            obs_files = [ '{:s}/{:s}.{:s}'.format(
                obs_dir, station_id, x['code']) for x in channels ]
            syn_files = [ '{:s}/{:s}.{:2s}{:1s}{:s}'.format(
                syn_dir, station_id, syn_band_code, x, syn_suffix) 
                for x in syn_orientation_codes ]

            # read in obs, syn seismograms
            try:
                obs_st  = read(obs_files[0])
                obs_st += read(obs_files[1])
                obs_st += read(obs_files[2])
                syn_st  = read(syn_files[0])
                syn_st += read(syn_files[1])
                syn_st += read(syn_files[2])
            except:
                print '[WARNING] %s:%s: error read obs/syn files, SKIP' \
                        % (event_id, station_id)
                station['stat']['code'] = -1
                station['stat']['msg'] = "error read file"
                continue

            # filter obs seismograms
            window_param = station['window_param']

            taper_param = window_param['taper']
            taper_type = taper_param['type']
            taper_percentage = taper_param['percentage']
            #obs_st.taper(type=taper_type, max_percentage=taper_percentage)

            filter_param = window_param['filter']
            filter_type = filter_param['type']
            freqlim = filter_param['freqlim']
            ncorners = filter_param['ncorners']
            obs_st.detrend('linear')
            obs_st.filter(type=filter_type, freqmin=freqlim[0],
                    freqmax=freqlim[1], corners=ncorners, zerophase=True)

            # get time samples of syn seismograms
            tr = syn_st[0]
            syn_starttime = tr.stats.starttime
            syn_delta = tr.stats.delta
            syn_sampling_rate = tr.stats.sampling_rate
            syn_npts = tr.stats.npts
            syn_times = syn_delta*np.arange(syn_npts)
            skip = False
            for i in range(1,3):
                tr = syn_st[i]
                if tr.stats.starttime != syn_starttime \
                        or tr.stats.npts != syn_npts \
                        or tr.stats.delta != syn_delta: 
                    print '[ERROR] %s:%s: not equal time samples in'\
                          ' synthetic seismograms. Quit' \
                          % (event_id, station_id)
                    skip = True
                    break
            if skip:
                station['stat']['code'] = -1
                station['stat']['msg'] = "not equal time samples in syn"
                continue

            # interpolate obs seismograms onto time samples of syn seismograms 
            obs_ENZ = np.zeros((3, syn_npts))
            for i in range(3):
                tr = obs_st[i]
                obs_ENZ[i,:] = lanczos_interp1(tr.data, tr.stats.delta,
                        syn_times+(syn_starttime-tr.stats.starttime), na=20)
            # roate obs to ENZ 
            # projection matrix: obs = proj * ENZ => ZNE = inv(proj) * obs
            proj_matrix = np.zeros((3, 3))
            for i in range(3):
                channel = channels[i]
                sin_az = np.sin(np.deg2rad(channel['azimuth']))
                cos_az = np.cos(np.deg2rad(channel['azimuth']))
                sin_dip = np.sin(np.deg2rad(channel['dip']))
                cos_dip = np.cos(np.deg2rad(channel['dip']))
                # column vector = obs channel polarization 
                proj_matrix[i,0] = cos_dip*sin_az # proj to E
                proj_matrix[i,1] = cos_dip*cos_az # proj to N
                proj_matrix[i,2] = -sin_dip       # proj to Z
            # inverse projection matrix: ENZ = inv(proj) * obs
            inv_proj = np.linalg.inv(proj_matrix)
            obs_ENZ = np.dot(inv_proj, obs_ENZ)

            # interpolate obs seismograms into noise window
            noise_starttime = UTCDateTime(station['noise_window']['starttime'])
            noise_endtime = UTCDateTime(station['noise_window']['endtime'])
            noise_window_len = noise_endtime - noise_starttime
            noise_npts = int(noise_window_len / syn_delta)
            noise_times = syn_delta * np.arange(noise_npts)
            noise_ENZ = np.zeros((3, noise_npts))
            for i in range(3):
                tr = obs_st[i]
                noise_ENZ[i,:] = lanczos_interp1(tr.data, tr.stats.delta,
                        noise_times+(noise_starttime-tr.stats.starttime), na=20)
            # roatate to ENZ
            noise_ENZ = np.dot(inv_proj, noise_ENZ)
            # apply taper
            noise_ENZ *= _taper_(noise_npts, taper_type, taper_percentage)

            # filter syn seismograms
            #   pad zeros pre-event in case near epicenter stations
            syn_st.trim(starttime=syn_starttime-100.0, pad=True, 
                    fill_value=0.0)
            syn_st.filter(type=filter_type, freqmin=freqlim[0], 
                    freqmax=freqlim[1], corners=ncorners, zerophase=True)
            syn_st.trim(starttime=syn_starttime, pad=False)
            # get ENZ arrays
            syn_ENZ = np.zeros((3, syn_npts))
            for i in range(3):
                tr = syn_st[i]
                syn_ENZ[i,:] = tr.data

            # loop each signal window
            taper = np.zeros(syn_npts)
            for window_id in windows:
                window = windows[window_id]
                comp = window['component']
                cmpaz = window['azimuth']
                cmpdip = window['dip']
                window_starttime = UTCDateTime(window['starttime'])
                window_endtime = UTCDateTime(window['endtime'])
                window_len = window_endtime - window_starttime

                # make taper window
                win_b = window_starttime - syn_starttime
                win_e = window_endtime - syn_starttime
                win_ib = int(win_b * syn_sampling_rate)
                win_ie = int(win_e * syn_sampling_rate) + 1
                if win_ib < 0: win_ib = 0
                if win_ie > syn_npts: win_ie = syn_npts
                taper[:] = 0.0
                taper[win_ib:win_ie] = _taper_(win_ie-win_ib, 
                        taper_type, taper_percentage)
 
                # projection matrix
                proj_matrix[:,:] = 0.0 #reset to zero
                if comp in ['Z', 'R', 'T']:
                    sin_az = np.sin(np.deg2rad(cmpaz))
                    cos_az = np.cos(np.deg2rad(cmpaz))
                    sin_dip = np.sin(np.deg2rad(cmpdip))
                    cos_dip = np.cos(np.deg2rad(cmpdip))
                    n = np.array([ [cos_dip * sin_az], # cos(E, comp)
                                   [cos_dip * cos_az], # N, comp
                                   [-sin_dip] ])       # Z, comp
                    proj_matrix = np.dot(n, n.transpose())
                elif comp == 'H': # horizontal vector 2d
                    proj_matrix[0,0] = 1.0 # E
                    proj_matrix[1,1] = 1.0 # N
                    proj_matrix[2,2] = 0.0 # Z
                elif win == 'F': # full 3d vector
                    proj_matrix[0,0] = 1.0
                    proj_matrix[1,1] = 1.0
                    proj_matrix[2,2] = 1.0
                else:
                    print '[WARNING] %s:%s:%s unrecognized component code, SKIP' \
                            % (event_id, station_id, window_id)
                    continue

                # apply window taper and projection
                noise_ENZ_win = np.dot(proj_matrix, noise_ENZ)
                obs_ENZ_win = np.dot(proj_matrix, obs_ENZ) * taper
                syn_ENZ_win = np.dot(proj_matrix, syn_ENZ) * taper

                # measure SNR
                A_syn = np.sqrt(np.max(np.sum(syn_ENZ_win**2, axis=0)))
                A_obs = np.sqrt(np.max(np.sum(obs_ENZ_win**2, axis=0)))
                A_noise =  np.sqrt(np.max(np.sum(noise_ENZ_win**2, axis=0)))
                if A_obs==0: # data file may not containe the time window
                    print '[WARNING] %s:%s:%s empty obs trace, SKIP.' \
                            % (event_id, station_id, window_id)
                    continue
                if A_noise==0: # could occure when the data begin time is too close to the first arrival
                    print '[WARNING] %s:%s:%s empty noise trace, SKIP.' \
                            % (event_id, station_id, window_id)
                    continue
                snr = 20.0 * np.log10(A_obs/A_noise)
 
                # measure misfit between observed and synthetic seismograms
                # cross-correlation
                obs_norm2 = np.sum(obs_ENZ_win**2)
                obs_norm = np.sqrt(obs_norm2)
                syn_norm = np.sqrt(np.sum(syn_ENZ_win**2))
                cc = np.zeros(2*syn_npts-1)
                for i in range(3):
                    # NOTE the order (obs,syn) is important. The positive time on 
                    #   CC means shifting syn in the positive time direction
                    cc += scipy.signal.fftconvolve(
                            obs_ENZ_win[i,:], syn_ENZ_win[i,::-1], 'full')
                cc /= obs_norm * syn_norm
                # tshift>0: synthetic is shifted along the positive time direction
                cc_max_time_shift = window_len/2.0 #TODO: more reasonable choice?
                ncc = int(cc_max_time_shift / cc_delta)
                cc_times = np.arange(-ncc,ncc+1) * cc_delta
                # interpolate cc to finer time samples
                if syn_delta < cc_delta:
                    print '[WARNING] syn_deltat(%f) < cc_time_step(%f)' \
                            % (syn_delta, cc_delta)
                ti = (syn_npts-1)*syn_delta + cc_times # -(npts-1)*dt: begin time in cc
                cci = lanczos_interp1(cc, syn_delta, ti, na=20)
                # time shift at the maximum correlation
                imax = np.argmax(cci)
                cc_time_shift = cc_times[imax]
                cc_max = cci[imax]
                ar_max = cc_max * syn_norm / obs_norm # amplitude ratio syn/obs
                # zero-lag normalized correlation
                cc_0 = cci[ncc]
                ar_0 = cc_0 * syn_norm / obs_norm # amplitude ratio syn/obs 

                ##TODO make adjoint source
                #if output_adj:
                #    adj_ENZ =  

                # make measurment results 
                quality_dict = { 
                        'A_obs': A_obs, 'A_syn': A_syn, 'A_noise': A_noise,
                        'SNR': snr}
                misfit_dict = {
                        'cc_0': cc_0, 'cc_max': cc_max,
                        'ar_0': ar_0, 'ar_max': ar_max,
                        'cc_time_shift': cc_time_shift }

                # add/update measure results
                if 'misfit' not in window \
                        or not window['misfit']:
                    window['quality'] = quality_dict
                    window['misfit'] = misfit_dict
                    window['stat'] = {'code': 1, 'msg': "measured"}
                elif update:
                    window['quality'].update(quality_dict)
                    window['misfit'].update(misfit_dict)
                    window['stat'] = {'code': 1, 'msg': "updated"}
                else:
                    continue

                # DEBUG
                #t = syn_times
                #noise_b = noise_starttime - syn_starttime
                #for i in range(3):
                #    plt.subplot(411+i)
                #    if i == 0:
                #        plt.title('%s dt %.2f ccmax %.3f armax %.3f ' \
                #                'cc0 %.1f ar0 %.3f \nAobs %g Anoise %g snr %.1f' \
                #                % (station_id, cc_time_shift, 
                #                   cc_max, ar_max, cc_0, ar_0, A_obs, A_noise, snr) )
                #    A_plot = max([A_obs, A_syn])

                #    plt.plot(t, obs_ENZ[i,:]/A_plot, 'k', linewidth=0.2)
                #    plt.plot(noise_times+noise_b, noise_ENZ_win[i,:]/A_plot, 'b', linewidth=0.5)
                #    plt.plot(t, syn_ENZ[i,:]/A_plot, 'r', linewidth=0.2)
                #    plt.plot(t[win_ib:win_ie], obs_ENZ_win[i,win_ib:win_ie]/A_plot,
                #            'k', linewidth=1.0)
                #    plt.plot(t[win_ib:win_ie], syn_ENZ_win[i,win_ib:win_ie]/A_plot,
                #            'r', linewidth=1.0)
                #    plt.ylim((-1.5, 1.5))
                #    plt.xlim((noise_b, max(t)))
                #    plt.ylabel(syn_orientation_codes[i])

                #plt.subplot(414)
                #plt.plot(cc_times, cci, 'k-')
                #plt.xlim((min(cc_times), max(cc_times)))
                #plt.ylabel(window_id)
          
                #plt.show()


            #end for window_id in windows:
        #end for station_id in station_id_list:
    #end def setup_windows(self,


    def relocate_1d(self, event_id, window_id_list=['Z.p,P', 'T.s,S'],
        min_SNR=10.0, min_cc_0=0.75, min_cc_max=0.85 ):
        """relocate event using ray path in reference earth model
        """
        # check inputs
        events = self.data['events']
        if event_id not in events:
            print "[ERROR] %s does NOT exist. Exit" \
                    % (event_id)
            sys.exit()

        event = events[event_id]
        stations = event['stations']

        # select data
        sta_win_id_list = []
        for station_id in stations:
            station = stations[station_id]
            windows = station['windows']

            # skip bad station 
            if station['stat']['code'] < 0:
                #msg = station['stat']['msg']
                #print "[WARNING] %s:%s(%s) station not used, SKIP" \
                #        % (event_id, station_id, msg)
                continue

                meta = station['meta']

            for window_id in window_id_list:
                if window_id not in windows:
                    continue
                window = windows[window_id]

                if window['stat']['code'] != 1 or \
                        window['quality']['SNR'] < min_SNR or \
                        window['misfit']['cc_0'] < min_cc_0 or \
                        window['misfit']['cc_max'] < min_cc_max:
                    continue

                sta_win_id = (station_id, window_id)
                sta_win_id_list.append(sta_win_id)

        # create sensitivity matrix G in local NED coordinate
        # G * dm  = dt_cc
        # G: [[-px_1, -py_1, -pz_1, 1.0], # ray1
        #     [-px_2, -py_2, -pz_2, 1.0], # ray2
        #     ...]
        # dm: [dNorth(km), dEast, dDepth, dT(sec)]
        # dt_cc: [dt1, dt2, ...]
        n = len(sta_win_id_list)
        G = np.zeros((n, 4))
        dt_cc = np.zeros(n)
        R_Earth_km = 6371.0
        evdp = event['gcmt']['depth']
        for i in range(n):
            sta_win_id = sta_win_id_list[i]
            station_id = sta_win_id[0]
            window_id = sta_win_id[1]
    
            station = stations[station_id]
            meta = station['meta']
            window = station['windows'][window_id]
            phase = window['phase']
            misfit = window['misfit']

            azimuth = np.deg2rad(meta['azimuth'])
            takeoff_angle = phase['takeoff_angle']
            takeoff = np.deg2rad(takeoff_angle + 180.0*(takeoff_angle<0))
            ray_param = phase['ray_param']
            slowness = ray_param / (R_Earth_km - evdp) #unit: s/km
            # local coordinate: NED
            pd = np.cos(takeoff) * slowness
            pn = np.cos(azimuth) * np.sin(takeoff) * slowness
            pe = np.sin(azimuth) * np.sin(takeoff) * slowness
            # create sensitivity matrix 
            G[i,:] = [-pn, -pe, -pd, 1.0] # -p: from receiver to source
            dt_cc[i] = misfit['cc_time_shift']

        #linearized inversion (can be extended to second order using dynamic ray-tracing)
        dm, residual, rank, s = np.linalg.lstsq(G, dt_cc)

        print "[dNorth(km),dEast,dDepth,dT(sec)]= ", dm
        print "sum(dt_res**2)= ", residual
        print "rank(G)=", rank
        print "singular_value(G)=", s
        
        # convert dm from NED to ECEF coordinate
        evla = event['gcmt']['latitude']
        evlo = event['gcmt']['longitude']

        slat = np.sin(np.deg2rad(evla))
        clat = np.cos(np.deg2rad(evla))
        slon = np.sin(np.deg2rad(evlo))
        clon = np.cos(np.deg2rad(evlo))

        N = [-slat*clon, -slat*slon, clat]
        E = [-slon, clon, 0.0]
        D = [-clat*clon, -clat*slon, -slat]

        ev_dx = N[0]*dm[0] + E[0]*dm[1] + D[0]*dm[2]
        ev_dy = N[1]*dm[0] + E[1]*dm[1] + D[1]*dm[2]
        ev_dz = N[2]*dm[0] + E[2]*dm[1] + D[2]*dm[2]
        ev_dt = dm[3]

        # initialize pyproj objects
        geod = pyproj.Geod(ellps='WGS84')
        ecef = pyproj.Proj(proj='geocent', ellps='WGS84', datum='WGS84')
        lla = pyproj.Proj(proj='latlong', ellps='WGS84', datum='WGS84')

        # old location in ECEF (meters)
        evx, evy, evz = pyproj.transform(lla, ecef, evlo, evla, -1000.0*evdp)
        print "old_location= ", evla, evlo, evdp

        # new location in ECEF (meters)
        evx1 = evx + ev_dx*1000.0
        evy1 = evy + ev_dy*1000.0
        evz1 = evz + ev_dz*1000.0
        # in LLA
        evlo1, evla1, evalt1 = pyproj.transform(ecef, lla, evx1, evy1, evz1)
        evdp1 = -evalt1/1000.0
        print "new_location= ", evla1, evlo1, evdp1, ev_dt

        # residuals 
        print "mean/std(dt_cc)= ", np.mean(dt_cc), np.std(dt_cc)
        # linearized modelling
        dt_syn = G.dot(dm) 
        dt_res = dt_cc - dt_syn
        print "mean/std(dt_res)= ", np.mean(dt_res), np.std(dt_res)

        #return evlo1, evla1, evdp1, ev_dt, dm


    def plot_misfit(self, event_id, window_id, outfig=None):
        """Plot misfit for a certain event and window_id  
        """
        # dt_cc       | cc_0/cc_max V.S. dt_cc 
        #-------------|-----------------------
        # hist?       | cc_0/cc_max VS SNR

        # check inputs
        events = self.data['events']
        if event_id not in events:
            print "[ERROR] %s does NOT exist. Exit" \
                    % (event_id)
            sys.exit()
        event = events[event_id]
        stations = event['stations']

        # get list of data 
        #sta_win_id_list = []
        stla_list = []
        stlo_list = []
        cc_dt_list = []
        cc_0_list = []
        cc_max_list = []
        snr_list = []
        for station_id in stations:
            station = stations[station_id]
            windows = station['windows']

            # skip bad station 
            if station['stat']['code'] < 0:
                continue

            if window_id not in windows:
                continue

            window = windows[window_id]
            if window['stat']['code'] != 1:
                continue

            meta = station['meta']
            misfit = window['misfit']
            quality = window['quality']

            #sta_win_id = (station_id, window_id)
            #sta_win_id_list.append(sta_win_id)
            stla_list.append(meta['latitude'])
            stlo_list.append(meta['longitude'])
            cc_dt_list.append(misfit['cc_time_shift'])
            cc_0_list.append(misfit['cc_0'])
            cc_max_list.append(misfit['cc_max'])
            snr_list.append(quality['SNR'])

        # get event data
        gcmt = event['gcmt']
        evla = gcmt['latitude']
        evlo = gcmt['longitude']
        M = gcmt['moment_tensor']
        Mrr = M[0][0]
        Mtt = M[1][1]
        Mpp = M[2][2]
        Mrt = M[0][1]
        Mrp = M[0][2]
        Mtp = M[1][2]
        focmec = [ Mrr, Mtt, Mpp, Mrt, Mrp, Mtp ]

        # map range
        min_lat = min(min(stla_list), evla)
        max_lat = max(max(stla_list), evla)
        min_lon = min(min(stlo_list), evlo)
        max_lon = max(max(stlo_list), evlo)
        #lat_true_scale = np.mean(stla_list)
        lat_0 = np.mean(stla_list)
        lon_0 = np.mean(stlo_list)
        # 
        parallels = np.arange(0.,81,10.)
        meridians = np.arange(0.,351,10.)

        # figure size
        fig = plt.figure(figsize=(11, 8.5))
        str_title = '%s %s' % (event_id, window_id)
        fig.text(0.5, 0.95, str_title, size='x-large', 
                horizontalalignment='center')

        #------ cc_time_shift + SNR 
        ax = fig.add_axes([0.05, 0.5, 0.4, 0.35])
        ax.set_title("cc_time_shift + SNR")

        m = Basemap(projection='merc', resolution='l',
                llcrnrlat=min_lat, llcrnrlon=min_lon, 
                urcrnrlat=max_lat, urcrnrlon=max_lon,
                lat_0=lat_0, lon_0=lon_0 )
        m.drawcoastlines(linewidth=0.1)
        m.drawcountries(linewidth=0.1)
        m.drawparallels(parallels, linewidth=0.1, labels=[1,0,0,1])
        m.drawmeridians(meridians, linewidth=0.1, labels=[1,0,0,1])
        
        # cc_time_shift, SNR
        sx, sy = m(stlo_list, stla_list)
        size_list = [ 0.01 if x<0.01 else x for x in snr_list ]
        im = m.scatter(sx, sy, s=size_list, marker='o',
                c=cc_dt_list, cmap='seismic', edgecolor='black',
                linewidth=0.05)
        mean_amp = np.mean(cc_dt_list)
        std_amp = np.std(cc_dt_list)
        plot_amp = abs(mean_amp)+std_amp
        im.set_clim(-plot_amp, plot_amp)
        
        # focal mechanism
        sx, sy = m(evlo, evla)
        b = Beach(focmec, xy=(sx, sy), width=200000, linewidth=0.2, 
                facecolor='k')
        ax.add_collection(b)
        
        # colorbar
        cbar_ax = fig.add_axes([0.45, 0.6, 0.005, 0.2])
        fig.colorbar(im, cax=cbar_ax, orientation="vertical")
        cbar_ax.tick_params(labelsize=9) 
        
        #------ cc_max, SNR
        ax = fig.add_axes([0.05, 0.05, 0.4, 0.35])
        ax.set_title("cc_max + SNR")

        m = Basemap(projection='merc', resolution='l',
                llcrnrlat=min_lat, llcrnrlon=min_lon, 
                urcrnrlat=max_lat, urcrnrlon=max_lon,
                lat_0=lat_0, lon_0=lon_0 )
        m.drawcoastlines(linewidth=0.1)
        m.drawcountries(linewidth=0.1)
        m.drawparallels(parallels, linewidth=0.1, labels=[1,0,0,1])
        m.drawmeridians(meridians, linewidth=0.1, labels=[1,0,0,1])
        
        # cc_max, SNR 
        sx, sy = m(stlo_list, stla_list)
        #size_list = [ 20**x for x in cc_max_list ]
        size_list = [ 0.01 if x<0.01 else x for x in snr_list ]
        im = m.scatter(sx, sy, s=size_list, marker='o',
                c=cc_max_list, cmap='seismic', edgecolor='black',
                linewidth=0.05)
        im.set_clim(0.5, 1.0)
        
        # focal mechanism
        sx, sy = m(evlo, evla)
        b = Beach(focmec, xy=(sx, sy), width=200000, linewidth=0.2, 
                facecolor='k')
        ax.add_collection(b)
 
        #add colorbar
        cbar_ax = fig.add_axes([0.45, 0.15, 0.005, 0.2])
        fig.colorbar(im, cax=cbar_ax, orientation="vertical")
        cbar_ax.tick_params(labelsize=9) 

        #------ SNR v.s. cc_max
        ax = fig.add_axes([0.6, 0.65, 0.35, 0.2])
        plt.plot(snr_list, cc_max_list, 'k.')
        ax.set_xlim([min(snr_list), max(snr_list)])
        ax.set_ylim([min(cc_max_list), max(cc_max_list)])
        ax.set_xlabel("SNR")
        ax.set_ylabel("cc_max")

        #------ cc_0 v.s. cc_max
        ax = fig.add_axes([0.6, 0.375, 0.35, 0.2])
        im = ax.scatter(cc_0_list, cc_max_list, marker='o',
                c=cc_dt_list, cmap='seismic', edgecolor='none')
        mean_amp = np.mean(cc_dt_list)
        std_amp = np.std(cc_dt_list)
        plot_amp = abs(mean_amp)+std_amp
        im.set_clim(-plot_amp, plot_amp)
        ax.set_xlim([min(cc_0_list), max(cc_0_list)])
        ax.set_ylim([min(cc_max_list), max(cc_max_list)])
        ax.set_xlabel("cc_0")
        ax.set_ylabel("cc_max")

        #------ cc_dt v.s. cc_max 
        ax = fig.add_axes([0.6, 0.1, 0.35, 0.2])
        plt.plot(cc_dt_list, cc_max_list, 'k.')
        ax.set_xlim([min(cc_dt_list), max(cc_dt_list)])
        ax.set_ylim([min(cc_max_list), max(cc_max_list)])
        ax.set_xlabel("cc_dt")
        ax.set_ylabel("cc_max")

        ##------ histogram of dt_cc and dt_res
        #ax1 = fig.add_axes([0.5,0.28,0.4,0.15])
        #n, bins, patches = ax1.hist(dt_cc, 50, facecolor='green', alpha=0.75)
        #amp = max(abs(dt_cc))
        #ax1.set_xlim([-amp, amp])
        #ax1.set_title('dt_cc: mean=%.2f std=%.2f' % (np.mean(dt_cc), np.std(dt_cc)))
        #ax1.tick_params(labelsize=10) 
        #
        #ax2 = fig.add_axes([0.5,0.07,0.4,0.15])
        #n, bins, patches = ax2.hist(dt_res, 50, facecolor='green', alpha=0.75)
        #amp = max(abs(dt_cc))
        #ax2.set_xlim([-amp, amp])
        #ax2.set_title('dt_res: mean=%.2f std=%.2f' % (np.mean(dt_res), np.std(dt_res)))
        #ax2.set_xlabel('dt (sec)')
        #ax2.tick_params(labelsize=10)

        #------ save figure
        if not outfig:
            outfig = '%s.%s.pdf' % (event_id, window_id)
        fig.savefig(outfig, format='pdf')
        #fig.savefig("misfit.pdf", bbox_inches='tight', format='pdf')