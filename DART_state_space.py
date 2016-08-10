# Python module for DART diagnostic plots in state space.
#
# Lisa Neef, 4 June 2014


import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mpl_toolkits.basemap import Basemap
import datetime
import pandas as pd
import DART as dart
from netCDF4 import Dataset
import WACCM as waccm
import re
import ERA as era
import TEM as tem
import experiment_settings as es

## here are some common settings for the different subroutines

# list the 3d, 2d, 1d variables 
# TODO: fill this in with other common model variables 
var3d = ['U','US','V','VS','T','Z3','DELF']
var2d = ['PS','FLUT']
var1d = ['hyam','hybm','hyai','hybi']

# constants
H = 7.0    # 7.0km scale height 

def plot_diagnostic_globe(E,Ediff=None,projection='miller',clim=None,cbar='vertical',log_levels=None,ncolors=19,hostname='taurus',debug=False,colorbar_label=None,reverse_colors=False,stat_sig=None):

	"""
	plot a given state-space diagnostic on a given calendar day and for a given variable 
	field on the globe.
	We can also plot the difference between two fields by specifying another list of Experiment
	dictionaries called Ediff  


	To plot climatology fields or anomalies wrt climatology, make the field E['diagn'] 'climatology.XXX' or 'anomaly.XXX', 
	where 'XXX' some option for loading climatologies accepted by the subroutine ano in MJO.py (see that code for options)

	INPUTS:  
	E: an experimend dictionary given the variable and diagnostic to be plotted, along with level, lat, lon ranges, etc. 
	Ediff: the difference experiment to subtract out (default is None)
	projection: the map projection to use (default is "miller")
	clim: the colorbar limits. If the scale is divergent, the limits are set as [-clim,clim]. If it's sequential, we do [0,clim].
	cbar: the orientation of the colorbar. Allowed values are 'vertical'|'horizontal'|None
	log_levels: a list of the (logarithmic) levels to draw the contours on. If set to none, just draw regular linear levels. 
	hostname
	taurus
	debug
	colorbar_label: string with which to label the colorbar  
	reverse_colors: set to false to reverse the colors in the 
	ncolors: how many colors in the contours - default is 19
	stat_sig: a dictionary giving the settings for estimating statistical significance with boostrap.
		Entries in this dict are: 
			P: the probability level at which we estimate the confidence intervals
			nsamples: the number of bootstrap samples 
		If these things are set, we add shading to denote fields that are statistically significantly 
			different from zero -- so this actually only makes sense for anomaies. 
		if stat_sig is set to "None" (which is the default), just load the data and plot. 
	"""

	# if plotting a polar stereographic projection, it's better to return all lats and lons, and then 
	# cut off the unwanted regions with map limits -- otherwise we get artifical circles on a square map
	if (projection == 'npstere'): 
		if E['latrange'][0] < 0:
			boundinglat = 0
		else:
			boundinglat =  E['latrange'][0]
		E['latrange'] = [-90,90]
		E['lonrange'] = [0,361]

	if (projection == 'spstere'):
		boundinglat = E['latrange'][1]
		E['latrange'] = [-90,90]
		E['lonrange'] = [0,361]


	##-----load data------------------
	if stat_sig is None:
		# turn the requested diagnostic into an array 
		Vmatrix,lat,lon,lev,DRnew = DART_diagn_to_array(E,hostname=hostname,debug=debug)

		# average over the last dimension, which is time
		if len(DRnew) > 1:
			VV = np.nanmean(Vmatrix,axis=len(Vmatrix.shape)-1)	
		else:
			VV = np.squeeze(Vmatrix)

		# average over vertical levels  if the variable is 3D
		# -- unless we have already selected a single level in DART_diagn_to_array
		if (E['variable'] in var3d) and (type(lev) != np.float64) and (E['levrange'][0] != E['levrange'][1]):
			# find the level dimension
			nlev = len(lev)
			for dimlength,idim in zip(VV.shape,range(len(VV.shape))):
				if dimlength == nlev:
					levdim = idim
			M1 = np.mean(VV,axis=levdim)
		else:
			M1 = np.squeeze(VV)

		# if computing a difference to another field, load that here  
		if (Ediff != None):
			Vmatrix,lat,lon,lev,DRnew = DART_diagn_to_array(Ediff,hostname=hostname,debug=debug)
			if len(DRnew) > 1:
				VV = np.nanmean(Vmatrix,axis=len(Vmatrix.shape)-1)	
			else:
				VV = np.squeeze(Vmatrix)
			# average over vertical levels  if the variable is 3D
			if (E['variable'] in var3d) and (type(lev) != np.float64) and (E['levrange'][0] != E['levrange'][1]):
				M2 = np.mean(VV,axis=levdim)
			else:
				M2 = np.squeeze(VV)
			# subtract the difference field out from the primary field  
			M = M1-M2
		else:
			M = M1
	else:
		# if statistical significance stuff was defined, loop over entire ensemble 
		# and use bootstrap to compute confidence intervals

		# first look up the ensemble size for this experiment from an internal subroutine:
		N = es.get_ensemble_size_per_run(E['exp_name'])

		# initialize an empty list to hold the ensemble of averaged fields 
		Mlist = []

		# loop over the ensemble  
		for iens in range(N):
			import bootstrap as bs

			E['copystring'] = 'ensemble member '+str(iens+1)
			# retrieve data for this ensemble member
			Vmatrix,lat,lon,lev,DRnew = DART_diagn_to_array(E,hostname=hostname,debug=debug)
			# if there is more than one time, average over this dimension (it's always the last one)
			if len(DRnew) > 1:
				VV = np.nanmean(Vmatrix,axis=len(Vmatrix.shape)-1)	
			else:
				VV = Vmatrix
			# average over vertical levels  if the variable is 3D and hasn't been averaged yet 
			if E['variable'] in var3d and type(lev) != np.float64:
				# find the level dimension
				nlev = len(lev)
				for dimlength,idim in zip(VV.shape,len(VV.shape)):
					if dimlength == nlev:
						levdim = idim
				M1 = np.mean(VV,axis=levdim)
			else:
				M1 = np.squeeze(VV)
			# if computing a difference to another field, load that here  
			if (Ediff != None):
				Ediff['copystring'] = 'ensemble member '+str(iens+1)
				Vmatrix,lat,lon,lev,DRnew = DART_diagn_to_array(Ediff,hostname=hostname,debug=debug)
				if len(DRnew) > 1:
					VV = np.nanmean(Vmatrix,axis=len(Vmatrix.shape)-1)	
				else:
					VV = Vmatrix
				# average over vertical levels  if the variable is 3D
				if E['variable'] in var3d and type(lev) != np.float64:
					M2 = np.mean(VV,axis=levdim)
				else:
					M2 = np.squeeze(VV)
				# subtract the difference field out from the primary field  
				M = M1-M2
			else:
				M = M1
			
			# store the difference (or plain M1 field) in a list 
			Mlist.append(M)

		# turn the list of averaged fields into a matrix, where ensemble index is the first dimension
		Mmatrix = np.concatenate([M[np.newaxis,...] for M in Mlist], axis=0)

		# now apply bootstrap over the first dimension, which by construction is the ensemble  
		CI = bs.bootstrap(Mmatrix,stat_sig['nsamples'],np.mean,stat_sig['P'])

		# anomalies are significantly different from 0 if the confidence interval does not cross zero
		# we can estimate this by checking if there is a sign change
		LU = CI.lower*CI.upper
		sig = LU > 0		# this mask is True when CI.lower and CI.upper have the same sign  
		
		# also compute the ensemble average for plotting
		M = np.mean(Mmatrix,axis=0)

	##-----done loading data------------------

 	# set up a map projection
	if projection == 'miller':
		maxlat = np.min([E['latrange'][1],90.0])
		minlat = np.max([E['latrange'][0],-90.0])
		map = Basemap(projection='mill',llcrnrlat=minlat,urcrnrlat=maxlat,\
			    llcrnrlon=E['lonrange'][0],urcrnrlon=E['lonrange'][1],resolution='l')
	if 'stere' in projection:
		map = Basemap(projection=projection,boundinglat=boundinglat,lon_0=0,resolution='l')
	if projection == None:
		map = Basemap(projection='ortho',lat_0=54,lon_0=10,resolution='l')

        # draw coastlines, country boundaries, fill continents.
	coastline_width = 0.25
	if projection == 'miller':
		coastline_width = 1.0
	map.drawcoastlines(linewidth=coastline_width)
		

        # draw lat/lon grid lines every 30 degrees.
	map.drawmeridians(np.arange(0,360,30),linewidth=0.25)
	map.drawparallels(np.arange(-90,90,30),linewidth=0.25)

        # compute native map projection coordinates of lat/lon grid.
	X,Y = np.meshgrid(lon,lat)
	x, y = map(X, Y)

        # choose color map based on the variable in question
	colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff,reverse=reverse_colors)

	# specify the color limits 
	if clim is None:
		clim = np.nanmax(np.absolute(M))
	if debug:
		print('++++++clim+++++')
		print(clim)

	# set the contour levels - it depends on the color limits and the number of colors we have  
	if cmap_type == 'divergent':
		L  = np.linspace(start=-clim,stop=clim,num=ncolors)
	else:
		L  = np.linspace(start=0,stop=clim,num=ncolors)


        # contour data over the map.
	if (projection == 'ortho') or ('stere' in projection):
		if log_levels is not None:
			cs = map.contourf(x,y,M, norm=mpl.colors.LogNorm(vmin=log_levels[0],vmax=log_levels[len(log_levels)-1]),levels=log_levels,cmap=cmap)
		else:
			cs = map.contourf(x,y,M,levels=L,cmap=cmap,extend="both")
	if projection is 'miller':
		cs = map.contourf(x,y,M,L,cmap=cmap,extend="both")

	if (cbar is not None):
		if (clim > 1000) or (clim < 0.001):
			CB = plt.colorbar(cs, shrink=0.6, extend='both',format='%.1e', orientation=cbar)
		else:
			CB = plt.colorbar(cs, shrink=0.6, extend='both', orientation=cbar)
		if colorbar_label is not None:
			CB.set_label(colorbar_label)
		else:
			CB = None

	# if desired, add shading for statistical significance - this only works for when we plot anomalies
	if stat_sig is not None:
		colors = ["#ffffff","#636363"]
		cmap = mpl.colors.ListedColormap(colors, name='my_cmap')
		map.contourf(x,y,sig,cmap=cmap,alpha=0.3)
	else:
		sig = None

	# return the colorbar handle if available, the map handle, and the data
	return CB,map,M,sig

def plot_diagnostic_hovmoeller(E,Ediff=None,clim=None,cbar='vertical',log_levels=None,hostname='taurus',debug=False,colorbar_label=None):

	"""
	plot a given state-space diagnostic on a Hovmoeller plot, i.e. with time on the y-axis and 
	longitudeo on the x-axis.  
	We can also plot the difference between two fields by specifying another list of Experiment
	dictionaries called Ediff.  

	To plot climatology fields or anomalies wrt climatology, make the field E['diagn'] 'climatology.XXX' or 'anomaly.XXX', 
	where 'XXX' some option for loading climatologies accepted by the subroutine ano in MJO.py (see that code for options)

	INPUTS:  
	log_levels: a list of the (logarithmic) levels to draw the contours on. If set to none, just draw regular linear levels. 

	"""

	# generate an array from the requested diagnostic  
	Vmatrix,lat,lon,lev,DRnew = DART_diagn_to_array(E,hostname=hostname,debug=debug)

	# find the latidue dimension and average over it
	shape_tuple = Vmatrix.shape
	for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
		if dimlength == len(lat):
			latdim = ii
	Mlat = np.nanmean(Vmatrix,axis=latdim)

	# if it's a 3d variable, also average over the selected level range  
	if len(shape_tuple) > 3: 
		shape_tuple_2 = Mlat.shape
		for dimlength,ii in zip(shape_tuple_2,range(len(shape_tuple_2))):
			if dimlength == len(lev):
				levdim = ii
		M1 = np.nanmean(Mlat,axis=levdim)
	else:
		M1 = Mlat

	# if computing a difference to another field, load that here  
	if (Ediff != None):
		Vmatrix,lat,lon,lev = DART_diagn_to_array(Ediff,hostname=hostname,debug=debug)

		# find the latidue dimension and average over it
		shape_tuple = Vmatrix.shape
		for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
			if dimlength == len(lat):
				latdim = ii
		Mlat = np.nanmean(Vmatrix,axis=latdim)

		# if it's a 3d variable, also average over the selected level range  
		if lev is not None:
			shape_tuple_2 = Mlat.shape
			for dimlength,ii in zip(shape_tuple_2,range(len(shape_tuple_2))):
				if dimlength == len(lev):
					levdim = ii
			M2 = np.nanmean(Mlat,axis=levdim)
		else:
			M2 = Mlat

		# subtract the difference field out from the primary field  
		M = M1-M2
	else:
		M = M1

	#---plot settings----------------
	time = DRnew

        # choose color map based on the variable in question
	colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff)

	# specify the color limits 
	if clim is None:
		clim = np.nanmax(np.absolute(M))
	if debug:
		print('++++++clim+++++')
		print(clim)

	# set the contour levels - it depends on the color limits and the number of colors we have  
	if cmap_type == 'divergent':
		L  = np.linspace(start=-clim,stop=clim,num=11)
	else:
		L  = np.linspace(start=0,stop=clim,num=11)

        # contour plot 
	MT = np.transpose(M)
	cs = plt.contourf(lon,time,MT,L,cmap=cmap,extend="both")

	# date axis formatting 
	if len(time)>30:
		fmt = mdates.DateFormatter('%b-%d')
		plt.gca().yaxis.set_major_locator(mdates.AutoDateLocator())
		plt.gca().yaxis.set_major_formatter(fmt)
	else:
		fmt = mdates.DateFormatter('%b-%d')
		plt.gca().yaxis.set_major_locator(mdates.AutoDateLocator())
		plt.gca().yaxis.set_major_formatter(fmt)

	if cbar is not None:
		if (clim > 1000) or (clim < 0.001):
			CB = plt.colorbar(cs, shrink=0.8, extend='both',orientation=cbar,format='%.3f')
		else:
			CB = plt.colorbar(cs, shrink=0.8, extend='both',orientation=cbar)
		if colorbar_label is not None:
			CB.set_label(colorbar_label)
	else: 
		CB = None


	#plt.gca().invert_yaxis()
	plt.ylabel('Time')
	plt.xlabel('Longitude')
	#plt.axis('tight')
	return CB,cs,M


def plot_diagnostic_lev_time(E=dart.basic_experiment_dict(),Ediff=None,clim=None,cbar='vertical',colorbar_label=None,reverse_colors=False,scaling_factor=1.0,hostname='taurus',debug=False):

	"""
	Given a DART experiment dictionary E, plot the desired diagnostic as a function of vertical level and time, 
	averaging over the selected latitude and longitude ranges. 

	INPUTS:
	E: experiment dictionary defining the main diagnostic  
	Ediff: experiment dictionary for the difference experiment
	clim: color limits (single number, applied to both ends if the colormap is divergent)
	hostname: name of the computer on which the code is running
	cbar: how to do the colorbar -- choose 'vertical','horiztonal', or None
	reverse_colors: set to True to flip the colormap
	scaling_factor: factor by which to multiply the array to be plotted 
	"""

	# throw an error if the desired variable is 2 dimensional 
	if E['variable'].upper() not in var3d:
		print('Attempting to plot a two dimensional variable ('+E['variable']+') over level and latitude - need to pick a different variable!')
		return

	# load the desired DART diagnostic for the desired variable and daterange:
	Vmatrix,lat,lon,lev,new_daterange = DART_diagn_to_array(E,hostname=hostname,debug=debug)

	# figure out which dimension is longitude and then average over that dimension 
	# unless the data are already in zonal mean, in which case DART_diagn_to_array should have returned None for lon
	shape_tuple = Vmatrix.shape
	if debug:
		print('shape of array after concatenating dates:')
		print(shape_tuple)
	if lon is not None:
		for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
			if dimlength == len(lon):
				londim = ii
		Vlon = np.squeeze(np.mean(Vmatrix,axis=londim))
	else:
		Vlon = np.squeeze(Vmatrix)  
	if debug:
		print('shape of array after averaging out longitude:')
		print(Vlon.shape)

	# figure out which dimension is longitude and then average over that dimension 
	# unless the data are already in zonal mean, in which case DART_diagn_to_array should have returned None for lon
	shape_tuple = Vlon.shape
	if lat is not None:
		for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
			if dimlength == len(lat):
				latdim = ii
		Vlonlat = np.squeeze(np.mean(Vlon,axis=latdim))
	else:
		Vlonlat = Vlon
	if debug:
		print('shape of array after averaging out latitude:')
		print(Vlonlat.shape)

	# if computing a difference to another field, load that here  
	if (Ediff != None):

		# load the desired DART diagnostic for the difference experiment dictionary
		Vmatrix,lat,lon,lev,new_daterange = DART_diagn_to_array(Ediff,hostname=hostname,debug=debug)

		# average over longitudes 
		if lon is not None:
			Vlon2 = np.squeeze(np.mean(Vmatrix,axis=londim))
		else:
			Vlon2 = np.squeeze(Vmatrix)

		# average over latitudes
		if lat is not None:
			Vlonlat2 = np.squeeze(np.mean(Vlon2,axis=latdim))
		else:
			Vlonlat2 = np.squeeze(Vlon2)

		# subtract the difference field out from the primary field  
		M = Vlonlat-Vlonlat2
	else:
		M = Vlonlat

        # choose color map based on the variable in question
	colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff,reverse=reverse_colors)

	# set the contour levels - it depends on the color limits and the number of colors we have  
	if clim is None:
		clim = scaling_factor*np.nanmax(np.absolute(M[np.isfinite(M)]))

	if cmap_type == 'divergent':
		L  = np.linspace(start=-clim,stop=clim,num=11)
	else:
		L  = np.linspace(start=0,stop=clim,num=11)

        # contour data 
	t = new_daterange
	if debug:
		print('shape of the array to be plotted:')
		print(M.shape)
	cs = plt.contourf(t,lev,M*scaling_factor,L,cmap=cmap,extend="both")

	# fix the date exis
	if len(t)>30:
		fmt = mdates.DateFormatter('%b-%d')
		plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
		plt.gca().xaxis.set_major_formatter(fmt)
	else:
		fmt = mdates.DateFormatter('%b-%d')
		plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
		plt.gca().xaxis.set_major_formatter(fmt)
	#plt.xticks(rotation=45)

	# add a colorbar if desired 
	if cbar is not None:
		if (clim > 1000) or (clim < 0.001):
			CB = plt.colorbar(cs, shrink=0.8, extend='both',orientation=cbar,format='%.0e')
		else:
			CB = plt.colorbar(cs, shrink=0.8, extend='both',orientation=cbar)
		if colorbar_label is not None:
			CB.set_label(colorbar_label)
	else: 
		CB = None


	plt.xlabel('time')
	plt.ylabel('Pressure (hPa)')
	plt.yscale('log')
	plt.gca().invert_yaxis()
	plt.axis('tight')
	return cs,CB

def plot_diagnostic_lat_time(E=dart.basic_experiment_dict(),Ediff=None,daterange = dart.daterange(date_start=datetime.datetime(2009,1,1), periods=81, DT='1D'),clim=None,hostname='taurus',cbar=True,debug=False):

	# loop over the input date range
	for date, ii in zip(daterange,np.arange(0,len(daterange))):  


		# load the data over the desired latitude and longitude range  
		if (E['diagn'].lower() == 'covariance') or (E['diagn'].lower() == 'correlation') :
			if ii == 0:
				lev,lat,lon,Cov,Corr = dart.load_covariance_file(E,date,hostname,debug=debug)
				nlat = len(lat)
				refshape = Cov.shape
			else:
				dum1,dum2,dum3,Cov,Corr = dart.load_covariance_file(E,date,hostname,debug=debug)


			if E['diagn'].lower() == 'covariance':
				VV = Cov
			if E['diagn'].lower() == 'correlation':
				VV = Corr
		else:
			if ii == 0:
				lev,lat,lon,VV,P0,hybm,hyam = dart.load_DART_diagnostic_file(E,date,hostname=hostname,debug=debug)
				nlat = len(lat)
				refshape = VV.shape
			else:
				dum1,dum2,dum3,VV,P0,hybm,hyam = dart.load_DART_diagnostic_file(E,date,hostname=hostname,debug=debug)

		# if the file was not found, VV will be undefined, so put in empties
		if VV is None:
			VV = np.empty(shape=refshape)

		# average over latitude and (for 3d variables) vertical levels 
		if (E['variable']=='PS'):
			Mlonlev = np.mean(VV,axis=1)
		else:
			Mlon = np.mean(VV,axis=1)
			Mlonlev = np.mean(Mlon,axis=1)
		

		M1 = Mlonlev


		# repeat for the difference experiment
		if (Ediff != None):
			lev2,lat2,lon2,VV,P0,hybm,hyam = dart.load_DART_diagnostic_file(Ediff,date,hostname=hostname,debug=debug)
			if (E['variable']=='PS'):
				M2lonlev = np.mean(VV,axis=1)
			else:
				M2lon = np.mean(VV,axis=1)
				M2lonlev = np.mean(M2lon,axis=1)
			M2 = M2lonlev
			M = M1-M2
		else:
			M = M1


		# append the resulting vector to the larger array (or initialize it)
		if (ii==0) :
			MM = np.zeros(shape=(nlat, len(daterange)), dtype=float)
			names=[]
		MM[:,ii] = M

	# make a grid of levels and days
	t = daterange

        # choose color map based on the variable in question
	colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff)


        # contour data over the map.
	cs = plt.contourf(t,lat,MM,len(colors)-1,cmap=cmap,extend="both")
	plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
	plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
	plt.axis('tight')
	if cmap_type == 'divergent':
		if clim is None:
			clim = np.nanmax(np.absolute(MM))
		plt.clim([-clim,clim])
	if debug:
		print(cs.get_clim())
	if cbar:
		if (clim > 1000) or (clim < 0.001):
			CB = plt.colorbar(cs, shrink=0.8, extend='both',orientation='vertical',format='%.3f')
		else:
			CB = plt.colorbar(cs, shrink=0.8, extend='both',orientation='vertical')
	else:
		CB = None
	plt.xlabel('time')
	plt.ylabel('Latitude')

	# fix the date exis
	if len(t)>30:
		fmt = mdates.DateFormatter('%b-%d')
		plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
		plt.gca().xaxis.set_major_formatter(fmt)
	else:
		fmt = mdates.DateFormatter('%b-%d')
		plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
		plt.gca().xaxis.set_major_formatter(fmt)

	return cs,CB

def retrieve_state_space_ensemble(E,averaging=True,ensemble_members='all',include_truth=False,hostname='taurus',debug=False):

	"""
	retrieve the prior or posterior ensemble averaged over some region of the state,
	along with the truth (if desired), 
	for some DART experiment
	
	INPUTS:
	E: standard experiment dictionary 
	averaging: set to True to average over the input latitude, longitude, and level ranges (default=True).
	ensemble_members: set to "all" to request entire ensemble, or specify a list with the numbers of the ensemble members you want to plot  
	include_truth: set to True to include the true state for this run. Note that if the truth does not exist but is requested, this 
		subroutine will throw an error. 
	hostname
	debug
	"""

	# query the daterange of E
	daterange = E['daterange']

	# decide what ensemble members to loop over here - specific ones, or the whole set?
	if type(ensemble_members) is list:
		ens_list = ensemble_members
	else:
		N = es.get_ensemble_size_per_run(E['exp_name'])
		ens_list = np.arange(1,N+1)

	# loop over the ensemble members and timeseries for each ensemble member, and add to a list
	Eens = E.copy()
	VElist = []
	for iens in ens_list:
		if iens < 10:
			spacing = '      '
		else:
			spacing = '     '
		copystring = "ensemble member"+spacing+str(iens)		
		Eens['copystring'] = copystring

		Vmatrix,lat,lon,lev,new_daterange = DART_diagn_to_array(Eens,hostname=hostname,debug=debug)

		# for individual ensemble mmbers, DART_diagn_to_array leaves a length-1 dimension in the 0th
		# spot -- 
		# EDIT: don't think we need this step any longer, but need to check to make sure 
		#VV = np.squeeze(Vmatrix)
		VV=Vmatrix
			
		# if averaging, do that here
		if averaging:
			Mlat = np.mean(VV,axis=0)
			Mlatlon = np.mean(Mlat,axis=0)
			if E['variable'] != 'PS':
				Mlatlonlev = np.mean(Mlatlon,axis=0)
			else:
				Mlatlonlev = Mlatlon
		else:
			Mlatlonlev = VV

		# append ensemble member to list
		VElist.append(Mlatlonlev)


	# turn the list of ensemble states into a matrix 
	VE = np.concatenate([V[np.newaxis,...] for V in VElist], axis=0)

	# load the corresponding truth, if desired or if it exists
	if include_truth:
		Etr = E.copy()
		Etr['diagn'] = 'Truth'
		Etr['copystring'] = 'true state'

		Vmatrix,lat,lon,lev,new_daterange = DART_diagn_to_array(Etr,hostname=hostname,debug=debug)
		# for individual ensemble mmbers, DART_diagn_to_array leaves a length-1 dimension in the 0th
		# spot -- need to squeeze that out
		VV = np.squeeze(Vmatrix)

		# average the true state, if desired 
		if averaging:
			Mlat = np.mean(VV,axis=0)
			Mlatlon = np.mean(Mlat,axis=0)
			if E['variable'] != 'PS':
				VT = np.mean(Mlatlon,axis=0)
			else:
				VT = Mlatlon
		else:
			VT = VV
	else:
		VT = None

	# output
	return VE,VT,lev,lat,lon


def plot_state_space_ensemble(E=None,truth_option='ERA',color_choice=1,linewidth=1.0,alpha=1.0,linestyle='-',hostname='taurus',debug=False,show_legend=False,ensemble_members='all'):

	"""
	plot the prior or posterior ensemble averaged over some region of the state,
	along with the truth (if available), 
	for some DART experiment

	input truth_option chooses what to plot as the "truth" to compare the ensemble to: 
	'pmo': plots the reference (or "truth") state, available only for PMO experiments. 
	'ERA': plots corresponding ERA-40 or ERA-Interin data  
	None: plots no true state.  
	ensemble_members: set to "all" to request entire ensemble, or specify a list with the numbers of the ensemble members you want to plot  

	input color_choice chooses a different color palette: 
	1 = gray ensemble with black ensemble mean (boring but straightforward)
	2 = "helmholtz" blue (sort of)

	"""

	# retrieve the ensemble
	if truth_option == 'pmo':
		include_truth = True
		truth_label='Truth'
	else:
		include_truth = False
	VE,VT,lev,lat,lon = retrieve_state_space_ensemble(E=E,averaging=True,include_truth=include_truth,hostname=hostname,debug=debug,ensemble_members=ensemble_members)

	# retrieve ERA data if desired
	if truth_option=='ERA':
		VT,t_tr,lat2,lon2,lev2 = era.retrieve_era_averaged(E)
		truth_label='ERA'

	# set up a  time grid 
	t = E['daterange']
	if truth_option=='pmo':
		t_tr = t
		VT = VT[0,:]

	# if no color limits are specified, at least make them even on each side
	# change the default color cycle to colorbrewer colors, which look a lot nicer
	if color_choice == 1:
		# TODO: replace with call to moduel palettable to get colorbrewer colors back
		colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff,reverse=reverse_colors)
		#bmap = brewer2mpl.get_map('Dark2', 'qualitative', 7)
		color_ensemble = "#878482"
		color_truth = colors[0]
		color_mean = "#000000"
	if color_choice == 2:
		#bmap = brewer2mpl.get_map('YlGnBu', 'sequential', 9)
		# TODO: replace with call to moduel palettable to get colorbrewer colors back
		colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff,reverse=reverse_colors)
		color_ensemble = colors[4]
		color_mean = colors[7]
		color_truth = "#000000"

        # plot global diagnostic in in time
	N = VE.shape[0]
	VM = np.mean(VE,axis=0)
	cs = plt.plot(t,VE[0,:],color=color_ensemble,label='Ensemble')
	for iens in np.arange(1,N):
		cs = plt.plot(t,VE[iens,:],color=color_ensemble,label='_nolegend_')
	plt.hold(True)
	if truth_option is not None:
		cs = plt.plot(t_tr,VT,color=color_truth,linewidth=2.0,label=truth_label)
	plt.plot(t,VM,color=color_mean,label='Ensemble Mean',linewidth=linewidth,alpha=alpha,linestyle=linestyle)

	# show a legend if desired
	if show_legend:
		lg = plt.legend(loc='best')
		lg.draw_frame(False)
	else: 
		lg=None

	clim = E['clim']
	if E['clim'] is not None:
		plt.ylim(clim)
	plt.xlabel('time')

	# format the y-axis labels to be exponential if the limits are quite high
	if clim is not None:
		if (clim[1] > 100):
			ax = plt.gca()
			ax.ticklabel_format(axis='y', style='sci', scilimits=(-2,2))

	# format the x-axis labels to be dates
	if len(t) > 30:
		#plt.gca().xaxis.set_major_locator(mdates.MonthLocator(bymonthday=1,interval=1))
		plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
		#plt.gca().xaxis.set_minor_locator(mdates.DayLocator(interval=1))
	if len(t) < 10:
		plt.gca().xaxis.set_major_locator(mdates.DayLocator(bymonthday=range(len(t))))
	fmt = mdates.DateFormatter('%b-%d')
	plt.gca().xaxis.set_major_formatter(fmt)

	return VE,VT,t,lg

def plot_diagnostic_global_ave(EE=[],EEdiff=None,ylim=None,xlim=None,include_legend=True,colors=None,linestyles=None,markers=None,x_as_days=False,hostname='taurus',debug=False):

	"""
	plot a given state-space diagnostic for a given variable field,
	as a function of time only (averaging spatially)  
	We can also plot the difference between two fields by specifying another experiment structure 
	called Ediff  

	INPUTS:
	EE: a list of experiment dictionaries to loop over an plot
	EEdiff: a list of experiments to subtract from the experiments in EE
	ylim: y-limits of the figure
	xlim: x-limits of the figure - note that this is tricky if we use dates instead of numbers 
	include_legend: set to False to get rid of the legennd (default is True)
	colors: input a list of hex codes that give the colors of the experiments to plot 
		the default is "None" -- in this case, choose Colorbrewer qualitative colormap "Dark2"
	linestyles: input a list of linestyle strings that give the styles for each line plotted. 
		the default is "None" - in this case, all lines are plotted as plain lines  
	markers: input a list of marker strings that give the markers for each line plotted. 
		the default is "None" - in this case, all lines are plotted as plain lines  
	x_as_days: set to True to plot a count of days on the x-axis rather than dates

	"""

	# set up an array of global averages that's the length of the longest experiment  
	DR_all = []
	for E in EE:
		DR_all.append(len(E['daterange']))
	max_length_time = max(DR_all)
	nE = len(EE)
	MM = np.zeros(shape=(nE, max_length_time), dtype=float)

	# also set up an array that holds the day count for each experiment  
	if x_as_days:
		x = np.zeros(shape=(nE, max_length_time), dtype=float)
		x[:,:] = np.NAN
	else: 
		x = E['daterange']

	# loop over experiment dictionaries and load the timeseries of the desired diagnostic
	names = []
	for iE,E in zip(range(nE),EE):

		# store the name of this experiment
		names.append(E['title'])

		# TODO: instead of looping over dates, load the entire timeseries using this subroutine
		# for each experiment, load the desired DART diagnostic for the desired variable and daterange:
		#Vmatrix,lat,lon,lev,new_daterange = DART_diagn_to_array(E,hostname=hostname,debug=debug)

		# for each experiment loop over the input date range
		for date, ii in zip(E['daterange'],range(len(E['daterange']))):  

			# fill in the day count (if desired) 
			if x_as_days:
				dt = date-E['daterange'][0]	
				dtfrac = dt.days + dt.seconds/(24.0*60.0*60.0)
				x[iE,ii] = dtfrac

			# load the data over the desired latitude and longitude range  
			lev,lat,lon,VV,P0,hybm,hyam = dart.load_DART_diagnostic_file(E,date,hostname=hostname,debug=debug)


			# compute global average only if the file was found
			if VV is not None:
				# average over latitude, longitude, and level  
				Mlat = np.mean(VV,axis=0)
				Mlatlon = np.mean(Mlat,axis=0)
				if E['variable'] in var3d:
					Mlatlonlev = np.mean(Mlatlon,axis=0)
				if E['variable'] in var2d:
					Mlatlonlev = Mlatlon
				M1 = Mlatlonlev

				# repeat for the difference experiment
				if (EEdiff != None):
					Ediff = EEdiff[iE]
					lev2,lat2,lon2,VV,P0,hybm,hyam = dart.load_DART_diagnostic_file(Ediff,date,hostname=hostname,debug=debug)
					if VV is not None:
						M2lat = np.mean(VV,axis=0)
						M2latlon = np.mean(M2lat,axis=0)
						if E['variable'] in var3d:
							M2latlonlev = np.mean(M2latlon,axis=0)
						if E['variable'] in var2d:
							M2latlonlev = M2latlon
						M2 = M2latlonlev
						M = M1-M2
					else:
						M = np.NAN
				else:
					M = M1
			else:
				# if no file was found, just make the global average a NAN
				M = np.NAN

			# append the resulting vector to the larger array (or initialize it)
			MM[iE,ii] = M


	#------plotting----------

	# change the default color cycle to colorbrewer Dark2, or use what is supplied
	if colors is None:
		# TODO: replace with call to moduel palettable to get colorbrewer colors back
		colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff,reverse=reverse_colors)
		#bmap = brewer2mpl.get_map('Dark2', 'qualitative', 7)

	# set all line styles to a plain line if not previous specified  
	if linestyles == None:
		linestyles = ['-']*nE

	# set all markers to None unless previously specified  
	if markers is None:
		markers = [None]*nE

        # plot global diagnostic in in time
	MT = np.transpose(MM)
	if x_as_days:
		xT = np.transpose(x)
	for iE in np.arange(0,nE):
		y0 = MT[:,iE]
		y = y0[~np.isnan(y0)]
		if x_as_days:
			x0 = xT[:,iE]
			x = x0[~np.isnan(y0)]
		else:
			x = E['daterange']
		cs = plt.plot(x,y,color=colors[iE],linewidth=2,linestyle=linestyles[iE],marker=markers[iE])

	# include legend if desire
	if include_legend:
		lg = plt.legend(names,loc='best')
		lg.draw_frame(False)

	plt.xlabel('Time (Days)')
	if ylim is not None:
		plt.ylim(ylim)
	if xlim is not None:
		plt.xlim(xlim)

	# format the y-axis labels to be exponential if the limits are quite high
	if (ylim > 100):
		ax = plt.gca()
		ax.ticklabel_format(axis='y', style='sci', scilimits=(-2,2))

	if not x_as_days:
		# format the x-axis labels to be dates
		if len(x) > 30:
			plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
		if len(x) < 10:
			plt.gca().xaxis.set_major_locator(mdates.DayLocator(bymonthday=range(len(t))))
		fmt = mdates.DateFormatter('%b-%d')
		plt.gca().xaxis.set_major_formatter(fmt)

	return MT,x



def state_space_HCL_colormap(E,Ediff=None,reverse=False,ncol=19,debug=False):

	"""
	loads colormaps (not a matplotlib colormap, but just a list of colors)
	based on the HCL theory put forth in Stauffer et al 2014
	other sample color maps are available here:  http://hclwizard.org/why-hcl/  

	INPUTS:
	E: a DART experiment dictionary. Relevant entries are:
		variable: if the variable is a positive definite quantity, use a sequential colormap  
		extras: if this indicates a postitive definite quantity, use a sequential colormap  
	Ediff: the differenence experiment dictionary. Used to determine if we are taking a difference, in 
		which case we would want a divergent colormap. 
	reverse: flip the colormap -- default is False 
	ncol: how many colors? Currently only 11 and 19 are supported for divergent maps, and only 11 for 
		sequential maps. Default is 19. 
	"""

        # appropriate color maps for state space plots
	colors_sequential = False

	# sequential plot if plotting positive definite variables and not taking a difference  
	post_def_variables = ['Z3','PS','FLUT','T','Nsq','Q','O3']
	if (Ediff == None) and (E['variable'] in post_def_variables):
                colors_sequential = True

        # for square error plots, we want a sequential color map, but only if not taking a difference
	if (E['extras']=='MSE')and (Ediff == None):
		colors_sequential = True

        # for ensemble spread plots, we want a sequential color map, but only if not taking a diff
	if (E['copystring']=='ensemble spread') and (Ediff == None):
		colors_sequential = True

        # for ensemble variance plots, we want a sequential color map, but only if not taking a diff
	if (E['extras']=='ensemble variance scaled') and (Ediff == None):
		colors_sequential = True

	# if plotting the MJO variance, wnat a sequential colormap
	if (E['extras'] == 'MJO variance'):
		colors_sequential = True

	# if the diagnostic includes a climatological standard deviation, turn on sequential colormap
	if 'climatological_std' in E['diagn']:
		colors_sequential = True

	# if any of the above turned on the sequential colormap but we are looking at anomalies or correlations, turn it back off  
	if E['extras'] is not None:
		if 'Correlation' in E['extras']:
			colors_sequential = False
	if 'anomaly' in E['diagn']:
		colors_sequential = False

	# also turn off the sequential colors if the diagnostic is increment  
	if E['diagn'].lower()=='increment':
                colors_sequential = False

        # choose sequential or diverging colormap
	if colors_sequential:
		# yellow to blue
		colors = ("#F4EB94","#CEE389","#A4DA87","#74CF8C","#37C293","#00B39B",
			  "#00A1A0","#008CA1","#00749C","#005792","#202581")

		if debug:
			print('loading a sequential HCL colormap')
		type='sequential'
	else:
		#---red negative and blue positive with white center instead of gray--
		colordict = {11:("#D33F6A","#DB6581","#E28699","#E5A5B1","#E6C4C9","#FFFFFF","#FFFFFF","#C7CBE3","#ABB4E2","#8F9DE1","#7086E1","#4A6FE3"),
				 19:("#D33F6A","#DA5779","#E26C88","#E88197","#EE94A7","#F3A8B6",
					  "#F7BBC6","#FBCED6","#FDE2E6","#FFFFFF","#FFFFFF","#E4E7FB",
					  "#D3D8F7","#C1C9F4","#AFBAF1","#9DABED","#8B9CEA","#788DE6",
					  "#637EE4","#4A6FE3")}
		colors=colordict[ncol]

		if debug:
			print('loading a diverging HCL colormap')
		type='divergent'

	if reverse:
		colors = colors[::-1]

	cmap = mpl.colors.ListedColormap(colors, name='my_cmap')

	return colors,cmap,type



def compute_rank_hist(E=dart.basic_experiment_dict(),daterange=dart.daterange(datetime.datetime(2009,1,1),10,'1D'),space_or_time='both',hostname='taurus'):

	# given some experiment E, isolate the ensemble at the desired location  
	# (given by E's entried latrange, lonrange, and levrange), retrieve 
	# the truth at the same location, and compute a rank histogram over the 
	# desired date range.  
	# 
	# the paramter space_or_time determines whether we count our samples over a blog of time, or in space 
	# if the choice is 'space', the time where we count is the first date of the daterange
	if (space_or_time == 'space'):
		dates = daterange[0]
		averaging = False

	if (space_or_time == 'time'):
		averaging = True
		dates = daterange
	
	if (space_or_time == 'both'):
		averaging = False
		dates = daterange


	# loop over dates and retrieve the ensemble
	VE,VT,lev,lat,lon = retrieve_state_space_ensemble(E,dates,averaging,hostname)

	# from this compute the rank historgram
	bins,hist = dart.rank_hist(VE,VT[0,:])

	return bins,hist,dates


def plot_rank_hist(E=dart.basic_experiment_dict(),daterange=dart.daterange(datetime.datetime(2009,1,1),81,'1D'),space_or_time='space',hostname='taurus'):


	# compute the rank historgram over the desired date range
	bins,hist,dates = compute_rank_hist(E,daterange,space_or_time,hostname)

	# plot the histogram
	plt.bar(bins,hist,facecolor='#9999ff', edgecolor='#9999ff')
	plt.axis('tight')
	plt.xlabel('Rank')

	return bins,hist,dates

def compute_state_to_obs_covariance_field(E=dart.basic_experiment_dict(),date=datetime.datetime(2009,1,1),obs_name='ERP_LOD',hostname='taurus'):

	# Given a DART experiment, load the desired state-space diagnostic file and corresponding obs_epoch_XXX.nc file,
	# and then compute the field of covariances between every point in the field defined by latrange, lonrange, and levrange
	# (these are entries in the experiment dictionary, E), and the scalar observation.

	# first load the entire ensemble for the desired variable field
	#lev,lat,lon,VV = dart.load_DART_diagnostic_file(E,date,hostname)
	VV,VT,lev,lat,lon = retrieve_state_space_ensemble(E,date,False,hostname)

	# now load the obs epoch file corresponding to this date
	obs,copynames = dart.load_DART_obs_epoch_file(E,date,[obs_name],['ensemble member'],hostname)

	# compute the ensemble mean value for each point in the variable field
	VM = np.mean(VV,0)

	# compute the mean and standard deviation of the obs predicted by the ensemble
	obsM = np.mean(obs)
	eobs = obs-obsM
	sobs = np.std(obs)
	

	# 3D variables: loop over lev, lat, lon and compute the covariance with the observation
	if len(VV.shape) == 5:
		[N,nlev,nlat,nlon,nt] = VV.shape
		C = np.zeros(shape=(nlat,nlon,nlev,nt))
		R = C.copy()
		for ilev in range(nlev):
			for ilat in range(nlat):
				for ilon in range(nlon):
					Ctemp = np.zeros(shape = (1,N))
					for ii in range(N):
						dx = VV[ii,ilev,ilat,ilon,:]-VM[ilev,ilat,ilon,:]
						Ctemp[0,ii] = dx*eobs[0,ii]
					C[ilat,ilon,ilev,:] = np.mean(Ctemp)/(float(N)-1.)
					sx = np.std(VV[:,ilev,ilat,ilon,0])
					R[ilat,ilon,ilev,:] = C[ilat,ilon,ilev,:]/(sx*sobs)
						

	# 2D variables: loop over  lat and lon and compute the covariance with the observation
	if len(VV.shape) == 4:
		lev = np.nan
		[N,nlat,nlon,nt] = VV.shape
		C = np.zeros(shape=(nlat,nlon,nt))
		R = C.copy()
		for ilat in range(nlat):
			for ilon in range(nlon):
				c = 0
				for ii in range(N):
					dx = VV[ii,ilat,ilon,:]-VM[ilat,ilon,:]
					C[ilat,ilon,:] += (1/(N-1))*dx*eobs[0,ii]
				sx = np.std(VV[:,ilat,ilon,:])
				R[ilat,ilon,:] = C[ilat,ilon,:]/(sx*sobs)

	return C,R,lev,lat,lon


def make_state_to_obs_covariance_file(E,date=datetime.datetime(2009,1,1,0,0,0),obs_name='ERP_LOD',hostname='taurus'):

	# run through a set of DART runs and dates and compute the covariances between the state variables  
	# and a given observation, then save it as a netcdf file  

	# Compute the covariance and correlation fields
	C, R, lev0,lat0,lon0 = compute_state_to_obs_covariance_field(E,date,obs_name,hostname)

	# compute the gregorian day number for this date
	# note: we can also go higher res and return the 12-hourly analysis times, but that requires changing several other routines
	dt = date - datetime.datetime(1600,1,1,0,0,0)
	time0 = dt.days

	# save a netcdf file for each date and observation variable
	fname = E['exp_name']+'_'+'covariance_'+obs_name+'_'+E['variable']+'_'+date.strftime('%Y-%m-%d')+'.nc'
	ff = Dataset(fname, 'w', format='NETCDF4')
	lat = ff.createDimension('lat', len(lat0))
	lon = ff.createDimension('lon', len(lon0))
	time = ff.createDimension('time', 1)
	longitudes = ff.createVariable('lon','f4',('lon',))
	latitudes = ff.createVariable('lat','f4',('lat',))
	times = ff.createVariable('time','f4',('time',))
	if E['variable']=='PS':
		covar = ff.createVariable('Covariance','f8',('lat','lon','time'))
		correl = ff.createVariable('Correlation','f8',('lat','lon','time'))
	else:
		lev = ff.createDimension('lev', len(lev0))
		levels = ff.createVariable('lev','f4',('lev',))
		covar = ff.createVariable('Covariance','f8',('lat','lon','lev','time'))
		correl = ff.createVariable('Correlation','f8',('lat','lon','lev','time'))

	# fill in the variables
	latitudes[:] = lat0
	longitudes[:] = lon0
	times[:] = time0
	if E['variable']=='PS':
		covar[:,:,:] = C
		correl[:,:,:] = R
	else:
		levels[:] = lev0
		covar[:,:,:,:] = C
		correl[:,:,:,:] = R

	# add file attributes
	ff.description = 'Covariance and Correlatin between variable field '+E['variable']+' and observation ',obs_name
	ff.history = 'Created ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	ff.source = 'Python modlue DART_state_space.py'  
	latitudes.units = 'degrees north'
	longitudes.units = 'degrees west'
	times.units = 'Days since 1601-01-01'  
	if not E['variable']=='PS':
		levels.units = 'hPa'

	# close the file
	ff.close()
	print('Created file '+fname)
	
def compute_aefs_as_csv(E = dart.basic_experiment_dict(),date=datetime.datetime(2009,1,1),hostname='taurus',debug=False):

	# given a DART experiment, compute the three AEF excitation functions, and save as a csvfile  

	# list of excitation functions to compute
	AEFlist = ['X1','X2','X3']

	# list of the 3 variables which contribute to AAM excitation
	variable_list = ['US','VS','PS']

	# figure out which copy strings are in the state space vector
	copystring_list = es.get_expt_CopyMetaData_state_space(E)

	# initialize lists for the three AEFs
	X = []
	aef_name_list = []
	copystring_list_long = []

	# loop over the AEFs and compute each one  
	for AEF in AEFlist:

		# cycle over all the copies that are available in the state space vector
		for copystring in copystring_list:
			print('+++computing AEF '+AEF+' for '+copystring+' for experiment '+E['exp_name']+'------')

			E['copystring'] = copystring
			dum,Xtemp = aef_from_model_field(E,date,variables=variable_list,ERP=AEF,levels_mistake=False,integral_type='mass',hostname=hostname)
			X.append(sum(Xtemp))  
			aef_name_list.append(AEF)
			copystring_list_long.append(copystring)

	# also make columns for experiment name, diagnostic, and date
	nC = len(copystring_list)
	nAEF = len(AEFlist)
	datelist = np.repeat(date,nC*nAEF)
	exp_name_list = np.repeat(E['exp_name'],nC*nAEF)
	diagn_list = np.repeat(E['diagn'],nC*nAEF)

	# now stick every thing into a dictionary
	D = {'time':datelist,
		'experiment':exp_name_list,
		'diagnostic':diagn_list,
		'copystring':copystring_list_long,
		'AEF':X,
		'Parameter_Name':aef_name_list}

	# turn the dictionary into a pandas dataframe and export to a csv file
	DF = pd.DataFrame(D)
	file_out_name = E['exp_name']+'_'+'AEFs_'+E['diagn']+'_'+date.strftime('%Y-%m-%d-%H-%M-%S')+'.csv'
	DF.to_csv(file_out_name, sep='\t')
	print('Created file '+file_out_name)



def aef_from_model_field(E = dart.basic_experiment_dict(),date=datetime.datetime(2009,1,1),variables=['U'],ERP='X3',levels_mistake=False,integral_type='mass',hostname='taurus',debug=False):

	# given a DART experiment dictionary and a date, retrieve the model field for that day 
	# and compute the AAM excitation function (AEF) from that field.
	# the keyword levels_mistake is set to true to simulate a possible code mistake where pressure levels were flipped the wrong way 
	# relative to the wind fields

	# the  output AEFs will be in a list, corresponding to the variables given as input
	Xout = []

	# cycle over the input list of variables and compute the AEF for each one
	for variable in variables:
		# retrieve the desired field for tha day
		E['variable'] = variable
		if variable == 'U':
			E['variable'] = 'US'
		if variable == 'V':
			E['variable'] = 'VS'

		# load the variable field
		lev,lat,lon,VV,P0,hybm,hyam = dart.load_DART_diagnostic_file(E,date,hostname=hostname,debug=debug)

		# if doing the mass integral, we have to recreate the 3d pressure field from hybrid model levels
		if (integral_type is 'mass'):

			# recreate the 3D pressure field
			E2 = E.copy()
			E2['variable'] = 'PS'
			dum1,latps,lonps,PS,dum4,dum5,dum6 = dart.load_DART_diagnostic_file(E2,date,hostname=hostname,debug=debug)
			nlev = len(lev)
			nlat = len(latps)
			nlon = len(lonps)
			P = np.zeros(shape=(nlat,nlon,nlev))
			for k in range(nlev):
				for j in range(nlat):
					for i in range(nlon):
						dum = None
						P[j,i,k] = hyam[k]*P0[0] + hybm[k] * PS[j,i]
					
			
			# compute the integral
			#Xtemp = erp.aef_massintegral(field=VV,PS=PS,p=P,lat=lat,lon=lon,variable_name=variable,ERP=ERP)
			Xtemp = erp.aef_massintegral(VV=VV,PS=PS,p=P,lat=latps,lon=lonps,variable_name=variable,ERP=ERP)

		# if doing a volume integral, we need to make sure the levels array is in Pascal 
		if (integral_type is 'volume'):
			lev_Pa = lev*100
			# simulate a flipped levels error if desired
			if levels_mistake:
				lev_Pa = np.flipud(lev_Pa)

			# compute the integral
			Xtemp = erp.aef(field=VV,lev=lev_Pa,lat=lat,lon=lon,variable_name=variable,ERP=ERP)

		# append integrated value to the list
		Xout.append(Xtemp)


	# temporary test plot
	#plt.figure(1)
	#dm = stuff[94,142,:]
	#dm = stuff[2,2,:]
	#plt.plot(range(nlev),dm)
        #fig_name = 'test.pdf'
        #plt.savefig(fig_name, dpi=96)
        #plt.close(1)



	# return ouput
	return variables,Xout


def plot_compare_AEFintegrals_to_obs(E = dart.basic_experiment_dict(),daterange = dart.daterange(periods=30),ERP='X1',hostname='taurus'):

	# for a given DART experiment, integrate the dynamical fields to get AAM excitation functions (AEFs), 
	# and compare these to the AEF observations produced by the obs operator (obs_def_eam.f90) 
	#
	# this is mostly to check that the AEF operator was coded correctly.  
	E['copystring'] = 'ensemble member     29'
	variables=['U','V','PS']
	X = np.zeros(shape=(4,len(daterange)))
	Xbad = np.zeros(shape=(4,len(daterange)))
	Y = np.zeros(shape=(1,len(daterange)))

	# choose the observation name that goes with the desired ERP
	if ERP == 'X1':
		obs_name = 'ERP_PM1'
	if ERP == 'X2':
		obs_name = 'ERP_PM2'
	if ERP == 'X3':
		obs_name = 'ERP_LOD'

	# loop over the daterange and create timeseries of the AEFs, 
	# and load the corresponding observations
	for date,ii in zip(daterange,range(len(daterange))):
		vars,XX = aef_from_model_field(E,date,variables,ERP,False,hostname)
		vars,XXbad = aef_from_model_field(E,date,variables,ERP,True,hostname)
		X[0,ii] = XX[0]
		X[1,ii] = XX[1]
		X[2,ii] = XX[2]
		X[3,ii] = sum(XX)
		Xbad[0,ii] = XXbad[0]
		Xbad[1,ii] = XXbad[1]
		Xbad[2,ii] = XXbad[2]
		Xbad[3,ii] = sum(XXbad)

		# load the corresponding observation
		obs,cs = dart.load_DART_obs_epoch_file(E,date,[obs_name],None, hostname)
		Y[0,ii] = obs


	# plot it and export as pdf
	plt.close('all')
	plt.figure(1)
	plt.clf()

	ax1 = plt.subplot(121)
	t = [d.date() for d in daterange]

	# TODO: replace with call to moduel palettable to get colorbrewer colors back
	colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff,reverse=reverse_colors)
	#bmap = brewer2mpl.get_map('Dark2', 'qualitative', 7)
	plt.plot(t,Y[0,:],color=_colors[0])
	plt.hold(True)
	plt.plot(t,X[3,:],color=colors[1])
	plt.plot(t,Xbad[3,:],color=bmap.colors[2])
	plt.legend(['EAM Code','My integral','Integral with flipped p levels'],loc='best')


	ax2 = plt.subplot(121)
	plt.plot(t,Y[0,:]-np.mean(Y[0,:]),color=bmap.mpl_colors[0])
	plt.hold(True)
	plt.plot(t,X[0,:]-np.mean(X[0,:]),color=bmap.mpl_colors[1])
	plt.plot(t,Xbad[0,:]-np.mean(Xbad[0,:]),color=bmap.mpl_colors[2])
	plt.legend(['EAM Code Anomaly','U integral anomaly','U integral anom with error'],loc='best')

	fig_name = 'EAM_obs_operator_error_check_'+ERP+'.pdf'
	plt.savefig(fig_name, dpi=96)
	plt.close()


	#return X,Y,t,vars

def retrieve_obs_space_ensemble(E=dart.basic_experiment_dict(),daterange = dart.daterange(date_start=datetime.datetime(2009,1,1), periods=5, DT='1D'),averaging=True,hostname='taurus'):

	# retrieve the prior or posterior ensemble for some observation, given by E['obs_name'],
	# along with the truth (if available), 
	# for some DART experiment

	# NOTE: so far I'm just writing this for Earth rotation parameter obs, which have no spatial location -- 
	# still need to expand the code for spatially-distributed obs, and potentially add averaging  

	# query the ensemble size for this experiment
	N = dart.get_ensemble_size_per_run(E['exp_name'])

	# if the input daterange is a single date, we don't have to loop over files
	nT = len(daterange)
	sample_date = daterange[0]

	# initialize an empty array to hold the ensemble
	VE = np.zeros(shape=(N,nT))
	VT = np.zeros(shape=(1,nT))

	# loop over the input date range
	for date, ii in zip(daterange,np.arange(0,len(daterange))):  

		# load the ensemble  
		obs_ensemble,copynames = dart.load_DART_obs_epoch_file(E,date,[E['obs_name']],['ensemble member'], hostname)
		VE[:,ii] = obs_ensemble

		# load the true state  
		Etr = E.copy()
		Etr['diagn'] = 'Truth'
		obs_truth,copynames = dart.load_DART_obs_epoch_file(Etr,date,[Etr['obs_name']],['Truth'], hostname)
		print(obs_truth)
		VT[0,ii] = obs_truth

	# output
	return VE,VT

def plot_obs_space_ensemble(E = dart.basic_experiment_dict(),daterange = dart.daterange(periods=30),clim=None,hostname='taurus'):

	# plot the prior or posterior ensemble averaged over some region of the state,
	# along with the truth (if available), 
	# for some DART experiment

	# retrieve the ensemble
	VE,VT = retrieve_obs_space_ensemble(E=E,daterange=daterange,hostname=hostname)
#	if E['exp_name'] == 'PMO32':

	# compute the ensemble mean
	VM = np.mean(VE,axis=0)

	# set up a  time grid 
	t = daterange

	# if no color limits are specified, at least make them even on each side
	# change the default color cycle to colorbrewer colors, which look a lot nicer
	# TODO: replace with call to moduel palettable to get colorbrewer colors back
	colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff,reverse=reverse_colors)
	#bmap = brewer2mpl.get_map('Dark2', 'qualitative', 7)

        # plot global diagnostic in in time
	N = VE.shape[0]
	for iens in np.arange(0,N):
		cs = plt.plot(t,VE[iens,:],color="#878482")
	plt.hold(True)
	cs = plt.plot(t,VT[0,:],color=bmap.mpl_colors[3])
	cm = plt.plot(t,VM,color="#000000")
	#lg = plt.legend(names,loc='best')
	#lg.draw_frame(False)

	if clim is not None:
		plt.ylim([-clim,clim])
	plt.xlabel('time')

	# format the y-axis labels to be exponential if the limits are quite high
	if (clim > 100):
		ax = plt.gca()
		ax.ticklabel_format(axis='y', style='sci', scilimits=(-2,2))

	# format the x-axis labels to be dates
	if len(t) > 30:
		#plt.gca().xaxis.set_major_locator(mdates.MonthLocator(bymonthday=1,interval=1))
		plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
		plt.gca().xaxis.set_minor_locator(mdates.DayLocator(interval=1))
	if len(t) < 10:
		plt.gca().xaxis.set_major_locator(mdates.DayLocator(bymonthday=range(len(t))))
	fmt = mdates.DateFormatter('%b-%d')
	plt.gca().xaxis.set_major_formatter(fmt)

def plot_diagnostic_lon_time(E=dart.basic_experiment_dict(),Ediff=None,clim=None,hostname='taurus',cbar=True,debug=False):

	# loop over the input date range
	daterange=E['daterange']
	for date, ii in zip(daterange,np.arange(0,len(daterange))):  


		# load the data over the desired latitude and longitude range  
		if (E['diagn'].lower() == 'covariance') or (E['diagn'].lower() == 'correlation') :
			if ii == 0:
				lev,lat,lon,Cov,Corr = dart.load_covariance_file(E,date,hostname,debug=debug)
				nlat = len(lat)
				refshape = Cov.shape
			else:
				dum1,dum2,dum3,Cov,Corr = dart.load_covariance_file(E,date,hostname,debug=debug)


			if E['diagn'].lower() == 'covariance':
				VV = Cov
			if E['diagn'].lower() == 'correlation':
				VV = Corr
		else:
			if ii == 0:
				lev,lat,lon,VV,P0,hybm,hyam = dart.load_DART_diagnostic_file(E,date,hostname=hostname,debug=debug)
				nlon = len(lon)
				refshape = VV.shape
			else:
				dum1,dum2,dum3,VV,P0,hybm,hyam = dart.load_DART_diagnostic_file(E,date,hostname=hostname,debug=debug)

		# if the file was not found, VV will be undefined, so put in empties
		if VV is None:
			VV = np.empty(shape=refshape)

		# average over latitude and (for 3d variables) vertical levels 
		if (E['variable']=='PS'):
			Mlatlev = np.mean(VV,axis=0)
		else:
			Mlat = np.mean(VV,axis=0)
			Mlatlev = np.mean(Mlat,axis=1)
		

		M1 = Mlatlev


		# repeat for the difference experiment
		if (Ediff != None):
			lev2,lat2,lon2,VV,P0,hybm,hyam = dart.load_DART_diagnostic_file(Ediff,date,hostname=hostname,debug=debug)
			if (E['variable']=='PS'):
				M2latlev = np.mean(VV,axis=0)
			else:
				M2lat = np.mean(VV,axis=0)
				M2latlev = np.mean(M2lat,axis=1)
			M2 = M2latlev
			M = M1-M2
		else:
			M = M1


		# append the resulting vector to the larger array (or initialize it)
		if (ii==0) :
			MM = np.zeros(shape=(nlon, len(daterange)), dtype=float)
			names=[]
		MM[:,ii] = M

	# make a grid of levels and days
	#day = daterange.dayofyear
	#t = [d.date() for d in daterange]
	t = daterange

        # choose color map based on the variable in question
	#cmap = state_space_colormap(E,Ediff)
	colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff)


        # contour data over the map.
        #cs = plt.contourf(t,lat,MM,15,cmap=cmap)
        #cs = plt.contourf(t,lat,MM,len(colors)-1,colors=colors)
	MT = np.transpose(MM)
	cs = plt.contourf(lon,t,MT,len(colors)-1,cmap=cmap,extend="both")
	plt.axis('tight')
	if cmap_type == 'divergent':
		if clim is None:
			clim = np.nanmax(np.absolute(MM))
		plt.clim([-clim,clim])
	print(cs.get_clim())
	if cbar:
		if (clim > 1000) or (clim < 0.001):
			CB = plt.colorbar(cs, shrink=0.8, extend='both',orientation='vertical',format='%.3f')
		else:
			CB = plt.colorbar(cs, shrink=0.8, extend='both',orientation='vertical')
	else:
		CB = None
	plt.ylabel('time')
	plt.xlabel('Longitude')

	# fix the date exis
	if len(t)>30:
		fmt = mdates.DateFormatter('%b-%d')
		plt.gca().yaxis.set_major_locator(mdates.AutoDateLocator())
		#plt.gca().yaxis.set_major_locator(mdates.MonthLocator())
		#plt.gca().yaxis.set_minor_locator(mdates.DayLocator())
		plt.gca().yaxis.set_major_formatter(fmt)
	else:
		fmt = mdates.DateFormatter('%b-%d')
		plt.gca().yaxis.set_major_locator(mdates.AutoDateLocator())
		#plt.gca().yaxis.set_minor_locator(mdates.DayLocator())
		plt.gca().yaxis.set_major_formatter(fmt)

	return cs,CB

def read_aefs_from_csv_to_dataframe(E=dart.basic_experiment_dict(), hostname='taurus', debug=False):

	#read in pre-computed angular momentum excitation functions (AEFs) for a DART run defined in the dictionary E
	# the AEFs are stored in csv files computed using the subroutine compute_aefs_as_csv

	# find the file path for the given experiment
	if E['run_category'] == None:
		path_list,dum = dart.exp_paths(hostname,E['exp_name'])
	if E['run_category'] == 'NCAR':
		path,dum = dart.exp_paths_NCAR(hostname,E['exp_name'])
		path_list = [path]
	if E['run_category'] == 'ERPDA':
		path_list,dum = dart.exp_paths_old(hostname,E['exp_name'])

	# select the first date and figure out which directory has the files we need in it  
	date = E['daterange'][0]
	correct_filepath_found = False
	import os.path
	for path in path_list:
		if debug:
			print(path)
		ff = E['exp_name']+'_'+'AEFs_'+E['diagn']+'_'+date.strftime('%Y-%m-%d-%H-%M-%S')+'.csv'
		filename = path+'/'+ff
		if os.path.exists(filename):
			correct_filepath_found = True
			break

	if correct_filepath_found is False:
		if debug:
			print("***cannot find files that look like  "+ff+' in any of the above directories')
		return
	
	if debug:
		print("loading files from the following directory: ")
		print(path)

	# cycle over the given dates, load data, and stick into a dataframe
	for date in E['daterange']:

		ff = E['exp_name']+'_'+'AEFs_'+E['diagn']+'_'+date.strftime('%Y-%m-%d-%H-%M-%S')+'.csv'
		filename = path+'/'+ff
		if date == E['daterange'][0]:
			DF = pd.read_csv(filename,sep='\t')
		else:
			DF2 = pd.read_csv(filename,sep='\t')
			DF = pd.merge(DF,DF2,how='outer')

	return(DF)

def compute_DART_diagn_from_Wang_TEM_files(E,datetime_in,hostname='taurus',debug=False):

	"""
	For a given experiment dictionary and datetime, load the transformed Eulerian mean (TEM) 
	diagnostics 
	corresponging to the desired DART diagnostic.  

	This code is designed to read in TEM diagnostics computed by Wuke Wang, GEOMAR Kiel 
	"""

	import TEM as tem

	# load the file corresponding to the desired date 
	X,lat,lev = tem.load_Wang_TEM_file(E,datetime_in,hostname=hostname,verbose=debug)
	CS = E['copystring']

	# if looking at ERA data, we don't have ensemble members. Here just return the array
	if 'ERA' in E['exp_name']:
		Dout = np.squeeze(X)	
	else:
		# if the diagnostic is a single ensemble member, simply choose it out of the array and return 
		if 'ensemble member' in CS:
			ensindex = re.sub(r'ensemble member*','',CS).strip()
			Dout = np.squeeze(X[:,:,:,int(ensindex)-1])	
		# can also compute simple ensemble statistics: mean, standard deviation, etc (other still need to be added)
		if CS == 'ensemble mean':
			Dout = np.squeeze(np.nanmean(X,axis=3))
		if CS == 'ensemble std':
			Dout = np.squeeze(np.nanstd(X,axis=3))
		
		# or return entire ensemble 
		if CS=='ensemble':
			# need to make the ensemble the zeroth dimension insteadd 
			# of the 3rd 
			N = X.shape[3]
			Xlist = []
			for ii in range(N):
				Xlist.append(X[:,:,:,ii])
			Dout = np.concatenate([X[np.newaxis,...] for X in Xlist], axis=0)
			# squeeze out a potential extra time dimension
			Dout = np.squeeze(Dout)

	return Dout,lat,lev

def compute_DART_diagn_from_model_h_files(E,datetime_in,hostname='taurus',verbose=True):

	# compute ensemble mean or spread, or just retrieve an ensemble member  
	# from variables that are found in WACCM or CAM history files 
	CS = E['copystring']

	Xout = None
	lat = None
	lon = None
	lev = None

	# it's easy if the copy we want is a single ensemble member  
	if 'ensemble member' in CS:
		ensindex = re.sub(r'ensemble member*','',CS).strip()
		instance = int(ensindex)
		Xout,lat,lon,lev = waccm.load_WACCM_multi_instance_h_file(E,datetime_in,instance,hostname=hostname,verbose=verbose)
		if (Xout is None) or (lat is None) or (lon is None):
			datestr = datetime_in.strftime("%Y-%m-%d")
			if verbose:
				print("filling in None for experiment "+E['exp_name']+', instance '+str(instance)+', and date '+datestr)

	# ensemble mean also has a special precomputed file
	if (CS == 'ensemble mean'):
		instance = 'ensemble mean'
		Xout,lat,lon,lev = waccm.load_WACCM_multi_instance_h_file(E,datetime_in,instance,hostname=hostname,verbose=verbose)
		if (Xout is None) or (lat is None) or (lon is None):
			datestr = datetime_in.strftime("%Y-%m-%d")
			if verbose:
				print("filling in None for experiment "+E['exp_name']+', instance '+str(instance)+', and date '+datestr)

	# ensemble standard deviation also has a special precomputed file
	if (CS == 'ensemble std'):
		instance = 'ensemble std'
		Xout,lat,lon,lev = waccm.load_WACCM_multi_instance_h_file(E,datetime_in,instance,hostname=hostname,verbose=verbose)
		if (Xout is None) or (lat is None) or (lon is None):
			datestr = datetime_in.strftime("%Y-%m-%d")
			if verbose:
				print("filling in None for experiment "+E['exp_name']+', instance '+str(instance)+', and date '+datestr)

	# to return the entire ensemble, retrieve number of ensemble members and loop  
	if (CS == 'ensemble'):
		N = es.get_ensemble_size_per_run(E['exp_name'])
		Xlist=[]
		for iens in range(N):
			instance = iens+1
			Xs,lat,lon,lev = waccm.load_WACCM_multi_instance_h_file(E,datetime_in,instance,hostname=hostname,verbose=verbose)
			Xlist.append(Xs)
		# turn the list of arrays into a new array 
		Xout = np.concatenate([X[np.newaxis,...] for X in Xlist], axis=0)

	# print an error message if none of these worked 
	if Xout is None:
		print('compute_DART_diagn_from_model_h_files does not know what to do with copystring '+copystring)
		print('Returning None')
		return None,None,None,None
	else:
		return Xout,lat,lon,lev

def plot_diagnostic_lev_lat(E=dart.basic_experiment_dict(),Ediff=None,clim=None,L=None,hostname='taurus',cbar='vertical',reverse_colors=False,ncolors=19,colorbar_label=None,vertical_coord='log_levels',scaling_factor=1.0,debug=False):

	"""
	Retrieve a DART diagnostic (defined in the dictionary entry E['diagn']) over levels and latitude.  
	Whatever diagnostic is chosen, we average over all longitudes in E['lonrange'] and 
	all times in E['daterange']

	INPUTS:
	E: basic experiment dictionary
	Ediff: experiment dictionary for the difference experiment
	clim: color limits (single number, applied to both ends if the colormap is divergent)
	L: list of contour levels - default is none, which choses the levels evenly based on clim 
	hostname: name of the computer on which the code is running
	cbar: how to do the colorbar -- choose 'vertical','horiztonal', or None
	reverse_colors: set to True to flip the colormap
	ncolors: how many colors the colormap should have. Currently only supporting 11 and 18. 
	colorbar_label: string with which to label the colorbar  
	scaling_factor: factor by which to multiply the array to be plotted 
	vertical_coord: option for how to plot the vertical coordinate. These are your choices:
		'log_levels' (default) -- plot whatever the variable 'lev' gives (e.g. pressure in hPa) on a logarithmic scale 
		'levels' -- plot whatever the variable 'lev' gives (e.g. pressure in hPa) on a linear scale 
		'z' -- convert lev (assumed to be pressure) into log-pressure height coordinates uzing z=H*exp(p/p0) where p0 = 1000 hPa and H=7km  
		'TPbased': in this case, compute the height of each gridbox relative to the local tropopause and 
			plot everything on a "tropopause-based" grid, i.e. zt = z-ztrop-ztropmean 
	debug: set to True to get extra ouput
	"""

	# throw an error if the desired variable is 2 dimensional 
	if (E['variable'] == 'PS') or (E['variable'] == 'FLUT'):
		print('Attempting to plot a two dimensional variable ('+E['variable']+') over level and latitude - need to pick a different variable!')
		return

	# load the requested array, and the difference array if needed 
	Vmain0,lat,lon,lev0,new_daterange = DART_diagn_to_array(E,hostname=hostname,debug=debug)
	# convert to TP-based coordinates if requested 	
	if vertical_coord=='TPbased': 
		Vmain,lev=to_TPbased(E,Vmain0,lev0,hostname=hostname,debug=debug)
	else:
		Vmain=Vmain0
		lev=lev0
	if Ediff is not None:
		Vdiff0,lat,lon,lev0,new_daterange = DART_diagn_to_array(Ediff,hostname=hostname,debug=debug)
		# convert to TP-based coordinates if requested 	
		if vertical_coord=='TPbased': 
			Vdiff,lev=to_TPbased(E,Vdiff0,lev0,hostname=hostname,debug=debug)
		else:
			Vdiff=Vdiff0
			lev=lev0
		Vmatrix=Vmain-Vdiff
	else:
		Vmatrix=Vmain

	# and average over the last dimension, which is always time (by how we formed this array) 
	VV = np.nanmean(Vmatrix,axis=len(Vmatrix.shape)-1)	

	# figure out which dimension is longitude and then average over that dimension 
	# unless the data are already in zonal mean, in which case DART_diagn_to_array should have returned None for lon
	shape_tuple = VV.shape
	if lon is not None:
		for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
			if dimlength == len(lon):
				londim = ii
		M = np.squeeze(np.mean(VV,axis=londim))
	else:
		M = np.squeeze(VV)

        # choose a color map based on the variable in question
	colors,cmap,cmap_type = state_space_HCL_colormap(E,Ediff,reverse=reverse_colors,ncol=ncolors)

	if clim is None:
		clim = np.nanmax(np.absolute(M[np.isfinite(M)]))

	# if not already specified, 
	# set the contour levels - it depends on the color limits and the number of colors we have  
	if L is None:
		if cmap_type == 'divergent':
			L  = np.linspace(start=-clim,stop=clim,num=ncolors)
		else:
			L  = np.linspace(start=0,stop=clim,num=ncolors)

	# transpose the array if necessary  
	if M.shape[0]==len(lat):
		MT = np.transpose(M)
	else:
		MT = M

        # plot
	if len(MT.shape) < 2:
		print('plot_diagnostic_lev_lat: the derived array is not 2-dimensional. This is its shape:')
		print(MT.shape)
		print('Returning with nothing plotted...')
		return None,None

	if (MT.shape[0] != len(lev)) |  (MT.shape[1] != len(lat)):
		print("plot_diagnostic_lev_lat: the dimensions of the derived array don't match the level and latitude arrays we are plotting against. Here are their shapes:")
		print(MT.shape)
		print(len(lev))
		print(len(lat))
		print('Returning with nothing plotted...')
		return None,None

	# compute vertical coordinate depending on choice of pressure or altitude 
	if 'levels' in vertical_coord:
		y=lev
		ylabel = 'Level (hPa)'
	if vertical_coord=='z':
		H=7.0
		p0=1000.0 
		y = H*np.log(p0/lev)
		ylabel = 'log-p height (km)'
	if vertical_coord=='TPbased':
		#from matplotlib import rcParams
		#rcParams['text.usetex'] = True
		y=lev
		ylabel='z (TP-based) (km)'

	cs = plt.contourf(lat,y,scaling_factor*MT,L,cmap=cmap,extend="both")

	# add a colorbar if desired 
	if cbar is not None:
		if (clim > 1000) or (clim < 0.01):
			CB = plt.colorbar(cs, shrink=0.8, extend='both',orientation=cbar,format='%.0e')
		else:
			CB = plt.colorbar(cs, shrink=0.8, extend='both',orientation=cbar)
		if colorbar_label is not None:
			CB.set_label(colorbar_label)
	else: 
		CB = None


	# axis labels 
	plt.xlabel('Latitude')
	plt.ylabel(ylabel)
	if vertical_coord=='log_levels':
		plt.yscale('log')
	if 'levels' in vertical_coord:
		plt.gca().invert_yaxis()

	# make sure the axes only go as far as the ranges in E
	plt.ylim(E['levrange'])
	plt.xlim(E['latrange'])

	# return the colorbar handle if available, so we can adjust it later
	return CB,M,L

def plot_diagnostic_lev_lat_quiver(E=dart.basic_experiment_dict(),Ediff=None,alpha=(1,1),scale_by_pressure=False,hostname='taurus',debug=False):

	"""
	Retrieve TWO DART diagnostics (defined in the dictionary entry E['diagn']) over levels and latitude,  
	and then plot them as a "quiver" plot (i.e. vector field). 
	In this case, E['variable'] should be a LIST or TUPLE of the two variable that we plot, e.g. FPHI and FZ for the components
	of EP flux, e.g. E['variable'] = (x,y), where x is the x-component of the vectors, and y the y-component. 
	Whatever diagnostic is chosen, we average over all longitudes in E['lonrange'] and 
	all times in E['daterange']

	INPUTS:
	E - experiment dictionary  
	Ediff - dictionary for the difference experiment (default is None)
	alpha - tuple of scaling factors for the horizontal and vertical components, 
		e.g. for EP flux alpha should be (4.899E-3,0)
	scale_by_pressure: set to True to scale the arrows by the pressure at each point
	"""

	# throw an error if the desired variable is 2 dimensional 
	if (E['variable'] == 'PS') or (E['variable'] == 'FLUT'):
		print('Attempting to plot a two dimensional variable ('+E['variable']+') over level and latitude - need to pick a different variable!')
		return

	# throw an error if E['variable'] is not a list or a tuple
	if (type(E['variable']) != tuple) and (type(E['variable']) != list):
		print('----Trying to make a vector field plot but the requested variable is not a tuple or a list, but rather:')	
		print(type(E['variable']))
		return

	# loop over the two variables and 
	# load the desired DART diagnostic for each variable and daterange:
	Mlist = []
	for vv in E['variable']:
		Etemp = E.copy()
		Etemp['variable'] = vv
		Vmatrix,lat,lon,lev,new_daterange = DART_diagn_to_array(Etemp,hostname=hostname,debug=debug)

		# if desired, scale the array by pressure (this is useful for EP flux vector)
		if scale_by_pressure:
			EP = E.copy()
			EP['variable'] = 'P'
			VP,dumlat,lonP,dumlev,dumdaterange = DART_diagn_to_array(EP,hostname=hostname,debug=debug)
			shape_tuple = VP.shape
			for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
				if dimlength == len(lonP):
					londim = ii
			VPlonave = np.squeeze(np.mean(VP,axis=londim))
			Vnorm = Vmatrix/VPlonave
		else:
			Vnorm = Vmatrix

		# average over the last dimension, which is always time (by how we formed this array) 
		VV = np.nanmean(Vnorm,axis=len(Vnorm.shape)-1)	
		
		# figure out which dimension is longitude and then average over that dimension 
		# unless the data are already in zonal mean, in which case DART_diagn_to_array should have returned None for lon
		shape_tuple = VV.shape
		if lon is not None:
			for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
				if dimlength == len(lon):
					londim = ii
			M1 = np.squeeze(np.mean(VV,axis=londim))
		else:
			M1 = np.squeeze(VV)

		# if computing a difference to another field, load that here  
		if (Ediff != None):
			Edtemp = Ediff.copy()
			Edtemp['variable'] = vv

			# load the desired DART diagnostic for the difference experiment dictionary
			Vmatrix,lat,lon,lev,new_daterange = DART_diagn_to_array(Edtemp,hostname=hostname,debug=debug)

			# if desired, scale the array by pressure (this is useful for EP flux vector)
			if scale_by_pressure:
				EdiffP = Ediff.copy()
				EdiffP['variable'] = 'P'
				VP,dumlat,lonP,dumlev,dumdaterange = DART_diagn_to_array(EdiffP,hostname=hostname,debug=debug)
				shape_tuple = VP.shape
				for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
					if dimlength == len(lonP):
						londim = ii
				VPlonave = np.squeeze(np.mean(VP,axis=londim))
				Vnorm = Vmatrix/VPlonave
			else:
				Vnorm = Vmatrix

			# average over time 
			VV = np.nanmean(Vnorm,axis=len(Vnorm.shape)-1)	

			# average over longitudes 
			if lon is not None:
				M2 = np.squeeze(np.mean(VV,axis=londim))
			else:
				M2 = np.squeeze(VV)

			# subtract the difference field out from the primary field  
			M = M1-M2
		else:
			M = M1

		# transpose the array if necessary  
		if M.shape[0]==len(lat):
			MT = np.transpose(M)
		else:
			MT = M

		# MT is the field we want to plot --> append it to the list
		Mlist.append(MT)

	# create a mesh
	X,Y = np.meshgrid(lat,lev)


        # plot
	plt.quiver(X,Y,alpha[0]*Mlist[0],alpha[1]*Mlist[1],pivot='mid', units='inches')


	# axis labels 
	plt.xlabel('Latitude')
	plt.ylabel('Pressure (hPa)')
	plt.yscale('log')
	plt.gca().invert_yaxis()

	# make sure the axes only go as far as the ranges in E
	plt.ylim(E['levrange'])
	plt.xlim(E['latrange'])

	# return the colorbar handle if available, so we can adjust it later
	return Mlist

def Nsq(E,date,hostname='taurus',debug=False):

	"""
	given a DART experiment dictionary on a certain date and time, compute the buoyancy frequency as a 3D field 

	**main calculation:**  
	N2 = (g/theta)*dtheta/dz 
	where theta = T(p_ref/p)^K is the potential temperature 
	K = R/cp 
	T = Temperature 
	p_ref = reference pressure (here using P0 = 1000.0 in WACCM data) 
	p = pressure  
	"""


	# if the data are on hybrid levels, check if pressure data are available somewhere 
	# otherwise, reconstruct the pressure field at each point from hybrid model variables 
	if (E['levtype']=='hybrid') or (E['levtype']=='model_levels'):
		H = dict()
		EP = E.copy()
		ET = E.copy()
		EP['variable']='P'
		ET['variable']='T'
		# for ERA data, use one of the subroutines in the ERA module to load pressure and temp:
		if 'ERA' in E['exp_name']:
			import ERA as era
			import re
			resol = float(re.sub('\ERA', '',E['exp_name']))
			P,lat,lon,lev,time2 = era.load_ERA_file(EP,date,resol=resol,hostname=hostname,verbose=debug)
			T,lat,lon,lev,time2 = era.load_ERA_file(ET,date,resol=resol,hostname=hostname,verbose=debug)
		else:
			# for DART runs, look for P and T in DART diagnostic files: 
			lev,lat,lon,P,P0,hybm,hyam = dart.load_DART_diagnostic_file(EP,date,debug=debug)
			lev,lat,lon,T,P0,hybm,hyam = dart.load_DART_diagnostic_file(ET,date,debug=debug)
			# TODO: if P is not in a DART diagnostic file, it could also be in a model history file, 
			# so need to add a line of code to try looking for that as well 
		if P is None:
			if debug:
				print('Pressure not available for requested date - recreating from hybrid levels (this takes a while....)')
			# special subroutine if we are dealing with ERA data, where usually log(Ps) is available insted of PS  
			if 'ERA' in E['exp_name']:
				P,lat,lon,lev = era.P_from_hybrid_levels_era(E,date,hostname=hostname,debug=debug)
			else:
				# otherwise, construct pressure the way it's done in CAM/WACCM
				# TODO: make this depend on the model input, so that we can more easily 
				# add settings for other models later  
				P,lat,lon,lev = P_from_hybrid_levels(E,date,hostname=hostname,debug=debug)


# if the data are on pressure levels, simply retrieve the pressure grid and turn it into a 3d field  
# TODO: add code for loading DART/WACCM output on constant pressure levels. Right now this 
	# only works for ERA data. 
	if E['levtype']=='pressure_levels':
		varlist = ['T','Z3']
		H = dict()
		if ('ERA' in E['exp_name']):
			import ERA as era
			for vname in varlist:
				Etemp = E.copy()
				Etemp['variable']=vname
				import re
				resol = float(re.sub('\ERA', '',E['exp_name']))
				field,lat,lon,lev,time_out = era.load_ERA_file(Etemp,date,hostname=hostname,verbose=debug,resol=resol)
				H[vname]=np.squeeze(field)
			# 3D pressure array from 1D array
			nlat = len(lat)
			nlon = len(lon)
			P1 = np.repeat(lev[:,np.newaxis],nlat,axis=1)
			P = np.repeat(P1[:,:,np.newaxis],nlon,axis=2)
			T=H['T']

	# choose reference pressure as 1000 hPa, with units based on the max of the P array 
	if np.max(P) > 2000.0:
		P0 = 100000.0			# reference pressure 
	else:
		P0 = 1000.0			# reference pressure 

	# compute potential temperature  
	Rd = 286.9968933                # Gas constant for dry air        J/degree/kg
	g = 9.80616                     # Acceleration due to gravity       m/s^2
	cp = 1005.0                     # heat capacity at constant pressure    m^2/s^2*K
	theta = T*(P0/P)**(Rd/cp)

	# turn the 3d pressure array into a geometric height array 
	z = 7000.0*np.log(P0/P)

	# compute the vertical gradient in potential temperature 
	dZ = np.gradient(np.squeeze(z))	# 3D gradient of height (with respect to model level) 
	dthetadZ_3D = np.gradient(np.squeeze(theta),dZ[0])
	dthetadZ = dthetadZ_3D[0] # this is the vertical temperature gradient with respect to pressure 

	# compute the buoyancy frequency 
	N2 = (g/np.squeeze(theta))*dthetadZ

	return N2,lat,lon,lev


def P_from_hybrid_levels(E,date,hostname='taurus',debug=False):

	"""
	given a DART experiment dictionary on a certain date and time,
	recreate the pressure field given the hybrid model level parameters 
	**note:** this code was crafted for WACCM/CAM data, and returns a pressure array 
	that fits te latxlonxlev structure of WACCM/CAM history files. 
	"""

	# check whether the requested experiment uses a model with hybrid levels. 
	# right now this just returns if the experiment is ERA-Interm.
	# TODO: subroutine with a dictionary that shows 
	# whether a given experiment has hybrid levels 
	if E['exp_name'] == 'ERA':
		print('ERA data are not on hybrid levels --need to retrieve ERA pressure data instead of calling P_from_hybrid_levels')
		return None,None,None,None

	# reconstruct the pressure field at each point from hybrid model variables 
	varlist = ['hyam','hybm','P0','PS','T','Z3']
	H = dict()
	for vname in varlist:
		Ehyb = E.copy()
		Ehyb['variable'] = vname
		field,lat,lon,lev = compute_DART_diagn_from_model_h_files(Ehyb,date,verbose=debug)
		if vname == 'PS':
			H['lev'] = lev
			H['lat'] = lat
			H['lon'] = lon        
		H[vname]=field

	if lev is None:
		print(Ehyb)

	nlev = len(lev)
	nlat = len(lat)
	nlon = len(lon)
	P = np.zeros(shape = (nlat,nlon,nlev))
	for k in range(nlev):
		for i in range(nlon):
			for j in range(nlat):
				P[j,i,k] = H['hyam'][k]*H['P0'] + H['hybm'][k]* np.squeeze(H['PS'])[j,i]

	return P,lat,lon,lev

def bootstrapci_from_anomalies(E,P=95,nsamples=1000,hostname='taurus',debug=False):

	"""
	Given some DART experiment dictionary, retrieve anomalies with respect 
	to a certain climatology and for the entire ensemble, and 
	then use a bootstrap method to compute the confidence interval 
	of those anomalies.  

	To make this work, the diagnostic given in E needs to specify the percentage of 
	the confidence interval that we want, and what climatology we are computing the anomalies
	with respect to.  

	E['diagn'] should have the form 'anomaly.XXXX.bootstrapci.NN' where 
		XXXX = the code for the climatology being used ("NODA" is a good choice)  
		NN = the percentage where we want the confidence interval (e.g. '95'

	INPUTS:  
	E: a standard DART experiment dictionary 
	P: the percentage where we want the confidence interval  - default is 95
	nsamples: the number of samples for the boostrap algorithm - default is 10000

	"""

	# look up the ensemble size for this experiment
	N = es.get_ensemble_size_per_run(E['exp_name'])

	# extract the climatology option for the anomalies from the diagnostic
	climatology_option = E['diagn'].split('.')[1]
	
	# loop over the entire ensemble, compute the anomalies with respect to
	# the desired climatology, and append to a list  
	Alist = []
	for iens in range(N):
	    E['copystring'] = 'ensemble member '+str(iens+1)
	    AA,Xclim,lat,lon,lev,new_daterange = mjo.ano(E,climatology_option)
	    Alist.append(AA)

	# turn the arrays in the list into a matrix
	Amatrix = np.concatenate([A[np.newaxis,...] for A in Alist], axis=0)

	# now apply bootstrap.
	# note that this function applies np.mean over the first dimension, which we made the ensemble
	CI = bs.bootstrap(Amatrix,nsamples,np.mean,P)
	
	# we can also make a mask for statistical significance. 
	# anomalies where the confidence interval includes zero are not considered statistically significant at the P% level. 
	# we can tell where the CI crosses zero by there the lower and upper bounds have opposite signs, which means that 
	# their product will be negative
	L = CI.lower
	U = CI.upper
	LU = L*U
	sig = LU > 0

	return CI,sig

def DART_diagn_to_array(E,hostname='taurus',debug=False):

	"""
	This subroutine loops over the dates given in E['daterange'] and load the appropriate DART diagnostic for each date, 
	returning a numpy matrix of the relevant date.  

	The files we load depend on the desired DART diagnostic (given in E['diagn']), variable (E['variable']), and 
	any extra computations needed (E['extras'])  
	"""

	#----------------ANOMALIES------------------------------
	# if plotting anomalies from climatology, climatology, or a climatological standard deviation, 
	# can load these using the `stds` and `ano` rubroutines in MJO.py  
	if ('climatology' in E['diagn']) or ('anomaly' in  E['diagn']) or ('climatological_std' in E['diagn']):
		from MJO import ano,stds
		climatology_option = E['diagn'].split('.')[1]
		AA,Xclim,lat,lon,lev,new_daterange = ano(E,climatology_option,hostname,debug)	
		if 'climatology' in E['diagn']:
			Vmatrix = Xclim
		if 'anomaly' in E['diagn']:
			Vmatrix = AA
		if 'climatological_std' in E['diagn']:
			S,lat,lon,lev = stds(E,climatology_option,hostname,debug)	
			Vmatrix = S.reshape(AA.shape)
		return Vmatrix,lat,lon,lev,new_daterange

	#----------------ERA data -- deprecated------------------------------
	# can use an old routine for loading ERA data, but for consistency 
	# can also just loop over the dates as below 
	# if loading regular variables from ERA data, can load those using a subroutine from the ERA module.
	# in this case, we also don't have to loop over dates.
	#if (E['exp_name']=='ERA') and (E['variable'] in era_variables_list):
#		import ERA as era
#		VV,new_daterange,lat,lon,lev = era.retrieve_era_averaged(E,False,False,False,hostname,debug)
		# this SR returns an array with time in the first dimension. We want it in the last
		# dimension, so transpose
#		Vmatrix = VV.transpose()
#		return Vmatrix,lat,lon,lev,new_daterange
	# ERA buoyancy frequency can be calculated with the Nsq function 
#	if (E['exp_name']=='ERA') and (E['variable'] == 'Nsq'):
#		Vmatrix,lat,lon,lev = Nsq(E,date,hostname=hostname,debug=debug)
#		return Vmatrix,lat,lon,lev,E['daterange']

	#----------------OTHER DATA------------------------------

	# if loading variables that are saved in monthly means, change the input daterange 
	# to be monthly, and then only loop over those dates.
	# WACCM h0 files are always monthly, so for now use the h-file-lookup routine in the WACCM module
	# to figure out whether the requested variable is monthly
	#still need to make this able to handle other monthly variables and other models/systems 
	hnum = waccm.history_file_lookup(E)
	if hnum is None:
		DR = E['daterange']
	else:	
		if hnum == 0:
			# instead of days, loop over months  
			DR2 = E['daterange']
			DRm = [datetime.datetime(dd.year,dd.month,1,12,0) for dd in DR2]
			DR = list(set(DRm))
		else:
			DR = E['daterange']


	# if none of the above worked, we have to 
	# loop over the dates given in the experiment dictionary and load the desired data  
	Vlist = []
	Vshape = None
	for date in DR:

		# most --but not all-- ERA data are loaded by their own routine  
		era_variables_list = ['U','V','Z','T','MSLP','Z3','ptrop','Q','O3','Nsq','brunt']
		if 'ERA' in E['exp_name'] and E['variable'] in era_variables_list:
			if (E['variable'] == 'Nsq'):
				# ERA buoyancy frequency can be calculated with the Nsq function 
				V,lat,lon,lev = Nsq(E,date,hostname=hostname,debug=debug)
			if 'V' not in locals():
				# all other variables are loaded via a function in the ERA module:
				import ERA as era
				import re
				resol = float(re.sub('\ERA', '',E['exp_name']))
				V,lat,lon,lev,dum = era.load_ERA_file(E,date,resol=resol,hostname=hostname,verbose=debug)

		# for regular diagnostic, the file we retrieve depends on the variable in question  
		else:
			file_type_found = False
			# here are the different categories of variables:
			# TODO: subroutine that reads the control variables specific to each model/experiment
			dart_control_variables_list = ['US','VS','T','PS','Q','ptrop','theta','Nsq','brunt','P','ztrop']
			tem_variables_list = ['VSTAR','WSTAR','FPHI','FZ','DELF']
			dynamical_heating_rates_list = ['VTY','WS']

			# for covariances and correlations
			if (E['diagn'].lower() == 'covariance') or (E['diagn'].lower() == 'correlation') :
				lev,lat,lon,Cov,Corr = dart.load_covariance_file(E,date,hostname,debug=debug)
				if E['diagn'].lower() == 'covariance':
					V = Cov
				if E['diagn'].lower() == 'correlation':
					V = Corr
				file_type_found = True

			# DART control variables are in the Prior_Diag and Posterior_Diag files 
			if E['variable'] in dart_control_variables_list:
				lev,lat,lon,V,P0,hybm,hyam = dart.load_DART_diagnostic_file(E,date,hostname=hostname,debug=debug)
				# if the above returns an error (bc we can't find the DART output files), we can still look 
				# for the same data in model output files. 
				if V is None:
					file_type_found = False
					print('Cannot find variable '+E['variable']+' in DART output')
					print('for experiment '+E['exp_name'])
					print('---> looking for model output files instead')
				else:
					file_type_found = True

			# transformed Eulerian mean diagnostics have their own routine 
			if E['variable'].upper() in tem_variables_list+dynamical_heating_rates_list:
				V,lat,lev = compute_DART_diagn_from_Wang_TEM_files(E,date,hostname=hostname,debug=debug)
				lon = None
				file_type_found = True
				
			# another special case is the buoyancy frequency forcing term -d(wstar*Nsq)/dz, also computed
			# from a separate routine
			if (E['variable'] == 'Nsq_wstar_forcing') or (E['variable'] == 'Nsq_vstar_forcing'):
				import TIL as til
				V,lat,lev = til.Nsq_forcing_from_RC(E,date,hostname=hostname,debug=debug)
				lon = None
				file_type_found = True
			# similar buoyancy frequency forcing from diabaitcc heating 
			if 'Nsq_forcing_' in E['variable']: 
				import TIL as til
				V,lat,lev = til.Nsq_forcing_from_Q(E,date,hostname=hostname,debug=debug)
				lon = None
				file_type_found = True

			# it might be that pressure needs to be recreated from the hybrid model levels 
			# -- this can be done in a separate routine. Right now this is commented out because it's faster 
			# to just compute pressure in the format of DART diagnostic files and then read those in. 
			# TODO: build in some dynamic way to test whether Pressure is available or needs to be recreated 
			#if E['variable'] == 'P':
			#	V,lat,lon,lev = P_from_hybrid_levels(E,date,hostname=hostname,debug=debug)
			#	file_type_found = True

			# for all other variables, compute the diagnostic from model h files 
			if file_type_found is False:
				# another special case is buoyancy frequency -- this is computed in a separate routine 
				# but only if it wasn't previously found in DART output form 
				if E['variable'] == 'Nsq':
					V,lat,lon,lev = Nsq(E,date,hostname=hostname,debug=debug)

				# for WACCM and CAM runs, if we requested US or VS, have to change these to U and V, 
				# because that's what's in the WACCM output 
				if E['variable'] is 'US':
					E['variable'] = 'U'
					V,lat,lon,lev = compute_DART_diagn_from_model_h_files(E,date,hostname=hostname,verbose=debug)
				if E['variable'] is 'VS':
					E['variable'] = 'V'
					V,lat,lon,lev = compute_DART_diagn_from_model_h_files(E,date,hostname=hostname,verbose=debug)

				# another other variables, retrieve as-is from history files 
				if 'V' not in locals():
					V,lat,lon,lev = compute_DART_diagn_from_model_h_files(E,date,hostname=hostname,verbose=debug)

		# add the variable field just loaded to the list:
		Vlist.append(V)

		# store the dimensions of the array V one time 
		if (V is not None) and (Vshape is None):
			Vshape = V.shape

		# if Vlist still has length 0, we didn't find any data -- abort 
		if len(Vlist)>0:
			# if Vlist has length, 
			# remove any Nones that might be in there and check again 
			Vlist2 = [V for V in Vlist if V is not None]
			if len(Vlist2)>0:
				bad = [i for i, j in enumerate(Vlist) if j is None]
				new_daterange = [i for j, i in enumerate(E['daterange']) if j not in bad]
				# turn the list of variable fields into a matrix 
				Vmatrix = np.concatenate([V[..., np.newaxis] for V in Vlist2], axis=len(V.shape))
			else:
				d1 = E['daterange'][0].strftime("%Y-%m-%d")
				d2 = E['daterange'][len(E['daterange'])-1].strftime("%Y-%m-%d")
				print('Could not find any data for experiment '+E['exp_name']+' and variable '+E['variable']+' between dates '+d1+' and '+d2)
				return None,None,None,None,None
		else:
			d1 = E['daterange'][0].strftime("%Y-%m-%d")
			d2 = E['daterange'][len(E['daterange'])-1].strftime("%Y-%m-%d")
			print('Could not find any data for experiment '+E['exp_name']+' and variable '+E['variable']+' between dates '+d1+' and '+d2)
			return None,None,None,None,None
	return Vmatrix,lat,lon,lev,new_daterange

def plot_diagnostic_profiles(E=dart.basic_experiment_dict(),Ediff=None,color="#000000",linestyle='-',linewidth = 2,alpha=1.0,scaling_factor=1.0,hostname='taurus',vertical_coord='log_levels',debug=False):

	"""
	Plot a vertical profile of some DART diagnostic / variable, 
	averaged over the date, latitude, and longitude ranges given in the 
	experiment dictionary.

	Instead of the zonal or meridional mean, we can also take the max of one of those dimensions. 
	To do this, add the words 'lonmax' or 'latmax' to the E['extras'] entry of the experiment 
	dictionary.  

	INPUTS:
	E: DART experiment dictionary of the primary experiment/quantity that we want to plot 
	Ediff: DART experiment dictionary of the experiment/quantity that we want to subtract out  (default is None)  
	color, linestyle, linewidth, alpha: parameters for the plotting (optional) 
	scaling_factor: factor by which we multiply the profile to be plotted (default is 1.0)    
	hostname: the computer this is being run on (default is taurus)  
	vertical_coord: option for how to plot the vertical coordinate. These are your choices:
		'log_levels' (default) -- plot whatever the variable 'lev' gives (e.g. pressure in hPa) on a logarithmic scale 
		'levels' -- plot whatever the variable 'lev' gives (e.g. pressure in hPa) on a linear scale 
		'z' -- convert lev (assumed to be pressure) into log-pressure height coordinates uzing z=H*exp(p/p0) where p0 = 1000 hPa and H=7km  
		'TPbased': in this case, compute the height of each gridbox relative to the local tropopause and 
			plot everything on a "tropopause-based" grid, i.e. zt = z-ztrop-ztropmean 
	debug: set to True to print out extra output 
	"""
	daterange = E['daterange']

	# throw an error if the desired variable is 2 dimensional 
	if (E['variable'] == 'PS') or (E['variable'] == 'FLUT'):
		print('Attempting to plot a two dimensional variable ('+E['variable']+') over level and latitude - need to pick a different variable!')
		return

	# check if the desired variable is a sum
	if ('+' in E['variable']):
		variable_list = E['variable'].split('+')
	else:
		variable_list=[E['variable']]
	Vmatrix_list=[]
	for variable in variable_list:
		Etemp=E.copy()
		Etemp['variable']=variable
		# load the requested array, and the difference array if needed 
		Vmain0,lat,lon,lev0,new_daterange = DART_diagn_to_array(Etemp,hostname=hostname,debug=debug)
		# convert to TP-based coordinates if requested 	
		if vertical_coord=='TPbased': 
			Vmain,lev=to_TPbased(E,Vmain0,lev0,hostname=hostname,debug=debug)
		else:
			Vmain=Vmain0
			lev=lev0

		if Ediff is not None:
			Etempdiff=Ediff.copy()
			Etempdiff['variable']=variable
			Vdiff0,lat,lon,lev0,new_daterange = DART_diagn_to_array(Etempdiff,hostname=hostname,debug=debug)
			# convert to TP-based coordinates if requested 	
			if vertical_coord=='TPbased': 
				Vdiff,lev=to_TPbased(E,Vdiff0,lev0,hostname=hostname,debug=debug)
			else:
				Vdiff=Vdiff0
				lev=lev0
			Vmatrix=Vmain-Vdiff
		else:
			Vmatrix=Vmain
		Vmatrix_list.append(Vmatrix)

	if ('+' in E['variable']):
		Vmatrix = sum(V for V in Vmatrix_list)

	# average over the last dimension, which is always time (by how we formed this array) 
	VV = np.nanmean(Vmatrix,axis=len(Vmatrix.shape)-1)	

	# find the latidue dimension and average (or take the max, if that option is chosen)
	if lat is not None:
		shape_tuple = VV.shape
		for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
			if dimlength == len(lat):
				latdim = ii
		Mlat = np.nanmean(VV,axis=latdim)
		if E['extras'] is not None:
			if 'latmax' in E['extras']:
				Mlat = np.nanmax(VV,axis=latdim)
	else:
		Mlat = VV

	# find the longitude dimension and average (or take the max, if that option is chosen)
	if lon is not None:
		shape_tuple = Mlat.shape
		for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
			if dimlength == len(lon):
			    londim = ii
		Mlon = np.nanmean(Mlat,axis=londim)
		if E['extras'] is not None:
			if 'lonmax' in E['extras']:
				Mlon = np.nanmax(Mlat,axis=londim)
	else:
		Mlon = Mlat
	M = scaling_factor*np.squeeze(Mlon)

	# compute vertical coordinate depending on choice of pressure or altitude 
	if 'levels' in vertical_coord:
		y=lev
		ylabel = 'Level (hPa)'
	if vertical_coord=='z':
		H=7.0
		p0=1000.0 
		y = H*np.log(p0/lev)
		ylabel = 'log-p height (km)'
	if vertical_coord=='TPbased':
		#from matplotlib import rcParams
		#rcParams['text.usetex'] = True
		y=lev
		ylabel='z (TP-based) (km)'

        # plot the profile  - loop over copies if that dimension is there  
	# from the way DART_diagn_to_array works, copy is always the 0th dimension  
	if M.ndim == 2:
		nC = M.shape[0]
		for iC in range(nC):
			if type(color) is 'list':
				color2 = color[iC]
			else:
				color2=color 
			plt.plot(M[iC,:],y,color=color2,linestyle=linestyle,linewidth=linewidth,label=E['title'],alpha=alpha)
	else:
		plt.plot(M,y,color=color,linestyle=linestyle,linewidth=linewidth,label=E['title'],alpha=alpha)

	# improve axes and labels
	ax = plt.gca()
	xlim = ax.get_xlim()[1]
	ax.ticklabel_format(axis='x', style='sci', scilimits=(-2,2))
	plt.ylabel(ylabel)
	if vertical_coord=='log_levels':
		plt.yscale('log')
	if (vertical_coord=='log_levels') or (vertical_coord=='levels'):
		plt.gca().invert_yaxis()

	# make sure the axes only go as far as the ranges in E
	if 'levels' in vertical_coord:
		plt.ylim(E['levrange'])
	else:
		H=7.0
		p0 = 1000.0
		ylim0=H*np.log(p0/E['levrange'][0])
		if E['levrange'][1]==0:
			ylimf = np.max(y)
		else:
			ylimf=H*np.log(p0/E['levrange'][1])
		ylim=(ylim0,ylimf)
		plt.ylim(ylim)
	return M,y
	

def plot_diagnostic_lat(E=dart.basic_experiment_dict(),Ediff=None,color="#000000",linestyle='-',linewidth = 2,alpha=1.0,hostname='taurus',scaling_factor=1.0,log_levels=False,invert_yaxis=False,debug=False):

	"""
	Retrieve a DART diagnostic (defined in the dictionary entry E['diagn']) and plot it 
	as a function of latitude 
	Whatever diagnostic is chosen, we average over all longitudes in E['lonrange'] and 
	all times in E['daterange'], and if the quantity is 3d, average over vertical levels  

	INPUTS:
	E: basic experiment dictionary
	Ediff: experiment dictionary for the difference experiment
	hostname: name of the computer on which the code is running
	ncolors: how many colors the colormap should have. Currently only supporting 11 and 18. 
	colorbar_label: string with which to label the colorbar  
	scaling_factor: factor by which to multiply the array to be plotted 
	debug: set to True to get extra ouput
	"""

	# load the desired DART diagnostic for the desired variable and daterange:
	Vmatrix,lat,lon,lev,new_daterange = DART_diagn_to_array(E,hostname=hostname,debug=debug)

	# and average over the last dimension, which is always time (by how we formed this array) 
	VV = np.nanmean(Vmatrix,axis=len(Vmatrix.shape)-1)	

	# figure out which dimension is longitude and then average over that dimension 
	# unless the data are already in zonal mean, in which case DART_diagn_to_array should have returned None for lon
	shape_tuple = VV.shape
	if lon is not None:
		for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
			if dimlength == len(lon):
				londim = ii
		Mlon = np.squeeze(np.mean(VV,axis=londim))
	else:
		Mlon = np.squeeze(VV)

	# if it's a 3d variable, figure out which dimension is vertical levels and then average over that dimension  
	shape_tuple2 = Mlon.shape
	if lev is not None:
		for dimlength,ii in zip(shape_tuple2,range(len(shape_tuple2))):
			if dimlength == len(lev):
				levdim = ii
		Mlonlev = np.squeeze(np.mean(Mlon,axis=levdim))
	else:
		Mlonlev = np.squeeze(Mlon)

	# if computing a difference to another field, load that here  
	if (Ediff != None):

		# load the desired DART diagnostic for the difference experiment dictionary
		Vmatrix,lat,lon,lev,new_daterange = DART_diagn_to_array(Ediff,hostname=hostname,debug=debug)

		# average over time 
		VV = np.nanmean(Vmatrix,axis=len(Vmatrix.shape)-1)	

		# average over longitudes 
		# as before, look for the londim (it might be different this time) 
		shape_tuple = VV.shape
		if lon is not None:
			for dimlength,ii in zip(shape_tuple,range(len(shape_tuple))):
				if dimlength == len(lon):
					londim = ii
			Mlon2 = np.squeeze(np.mean(VV,axis=londim))
		else:
			Mlon2 = np.squeeze(VV)

		# average over vertical levels if needed 
		shape_tuple2 = Mlon2.shape
		if lev is not None:
			for dimlength,ii in zip(shape_tuple2,range(len(shape_tuple2))):
				if dimlength == len(lev):
					levdim = ii
			Mlonlev2 = np.squeeze(np.mean(Mlon2,axis=levdim))
		else:
			Mlonlev2 = np.squeeze(Mlon2)

		# subtract the difference field out from the primary field  
		M = Mlonlev-Mlonlev2
	else:
		M = Mlonlev



	# transpose the array if necessary  
	if M.shape[0]==len(lat):
		MT = np.transpose(M)
	else:
		MT = M

	# if we are plotting multiple copies (e.g. the entire ensemble), need to loop over them  
	# otherwise, the plot is simple
	if len(MT.shape) == 2:
		ncopies = MT.shape[0]
		for icopy in range(ncopies):
			plt.plot(lat,scaling_factor*MT[icopy,:],color=color,linestyle=linestyle,linewidth=linewidth,label=E['title'],alpha=alpha)
	else:
		plt.plot(lat,scaling_factor*MT,color=color,linestyle=linestyle,linewidth=linewidth,label=E['title'],alpha=alpha)

	# axis labels 
	plt.xlabel('Latitude')

	# vertical axis adjustments if desired (e.g. if plotting tropopause height) 
	if log_levels:
		plt.yscale('log')
	if invert_yaxis:
		plt.gca().invert_yaxis()

	# make sure the axes only go as far as the ranges in E
	plt.xlim(E['latrange'])

	return MT,lat

def to_TPbased(E,Vmatrix,lev,hostname='taurus',debug=False):

	"""
	This routine takes some multi-dimensional variable field and a corresponding array for vertical levels, 
	and transforms the vertical coordinate into altitudes defined relative to the local tropopause, plus
	the time-mean tropopause in that location, i.e. zt = z-ztrop-ztropmean 
	(See [Birner 2006](http://www.agu.org/pubs/crossref/2006/2005JD006301.shtml))

	After computing the TP-based height at each location, we run through all latitudes, 
	longitudes, times, and copies, and interpolate the tropopause-based heights 
	to a regular grid so that we can average. 
	The `interp1d` function creates a functional relationship between the variable in 
	Vmatrix and the TP-based coordinates, and the grid to which we interpolate has to be 
	within the bounds of this function (i.e. the min and max values of TP-based altitude 
	for each column).  -- Might have to play with this for your own data. 
 
	INPUTS:
	E: a DART experiment dictionary giving the details of the data that we are requesting 
	Vmatrix: a multi-dimensional model data grid, ideally the output of DART_diagn_to_array  
	lev: a vector of vertical level pressures. These can be in Pascal or hPa. 
	"""

	# given the data matrix, we have to retrieve several other things: 
	# and the climatological-mean tropopause height for every point on the grid. 
	#   this last one is most easily computed by using the ensemble mean of a corresponding 
	#   No-DA experiment. 
	#
	# First define all the things we need in experiment dictionaries, and then 
	# stick those into a list to loop over 

	# tropopause height of the experiment 
	Etrop=E.copy()
	Etrop['variable']='ptrop'
	Etrop['matrix_name']='ztrop'

	# the pressure field of the requested experiment 
	Ep=E.copy()
	Ep['variable']='P'
	Ep['matrix_name']='z'  

	# the climatological mean tropopause height (i.e. the tropopause height in the mean of the No-assim experiment)
	EtropNODA = Etrop.copy()
	EtropNODA['exp_name']= es.get_corresponding_NODA(Etrop['exp_name'])
	EtropNODA['copystring']='ensemble mean'
	EtropNODA['matrix_name']='ztropmean'

	# now loop over these experiment and retrieve the data, also converting pressures to altitudes 
	# stick these into a dictionary 
	EE = [Etrop,Ep,EtropNODA]
	Zdict = dict()
	for Etemp in EE:
		if Etemp is not None:
			V,dumlat,dumlon,dumlev,dumnew_daterange = DART_diagn_to_array(Etemp)
			if np.max(V) > 10000.0:     # this will be true if pressure units are Pascal
				P0=1.0E5
			else:                        # otherwise assume pressure is in hPa
				P0=1.0E3
			Z = H*np.log(P0/V)
			
			# for tropopause heights, convert 2d to 3d array by adding an additional dimension 
			if 'ztrop' in Etemp['matrix_name']:
				# find which is the vertical levels dimension 
				nlev = len(lev)
				levdim = list(Vmatrix.shape).index(nlev)  
				Zx = np.expand_dims(Z, axis=levdim)
				Z3d=np.broadcast_to(Zx,Vmatrix.shape)
			else:
				Z3d=Z
				       
			# add final array to dictionary 
			Zdict[Etemp['matrix_name']]=Z3d

	# now for each point, compute z-ztrop+ztropmean
	ZT = Zdict['z']-Zdict['ztrop']+Zdict['ztropmean']

	# create a regular grid 
	zTPgrid=np.arange(6.0,21.0, 1.0)

	# empty array to hold interpolated data
	Snew = list(Vmatrix.shape)
	Snew[3] = len(zTPgrid)
	Vnew = np.empty(shape=Snew)*np.nan

	# loop through Vmatrix and create interpolation function between each column and the corresponding heights 
	S=Vmatrix.shape

	from scipy.interpolate import interp1d
	for ii in range(S[0]):
		for jj in range(S[1]):
			for kk in range(S[2]):
				for ll in range(S[4]):
					Vcolumn = Vmatrix[ii,jj,kk,:,ll]
					ZTcolumn = ZT[ii,jj,kk,:,ll]

					# here is the interpolation function:
					f = interp1d(ZTcolumn,Vcolumn, kind='cubic')

					# check whether the sampled ZTcolumn covers the grid we interpolate to
					select = np.where(np.logical_and(zTPgrid>min(ZTcolumn), zTPgrid<max(ZTcolumn)))
					zTPnew=zTPgrid[select]
					Vnew[ii,jj,kk,select,ll] = f(zTPnew)
					
					# need to check whether the sampled ZTcolumn covers the 
					# grid to which we want to interpolate
					#if (np.min(zTPgrid) < np.min(ZTcolumn)) or (np.max(zTPgrid) > np.max(ZTcolumn)):
					#	Vnew[ii,jj,kk,:,ll] = np.nan
					#else:
					#	Vnew[ii,jj,kk,:,ll] = f(zTPgrid)

	return Vnew,zTPgrid
