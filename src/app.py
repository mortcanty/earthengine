#! /usr/bin/env python
import time, math, sys
import ee
from flask import Flask, render_template, request
from eeMad import imad, chi2cdf, radcal, radcalbatch
from eeWishart import omnibus

# Set to True for localhost, False for appengine dev_appserver or deploy
#------------
local = True
#------------

glbls = {'centerLon':8.5,'centerLat':50.05,
         'minLat':49.985,'maxLat':50.078,'minLon':8.444,'maxLon':8.682,
         'startDate':'2016-04-01','endDate':'2016-09-01',
         'startDate1':'2016-03-07','endDate1':'2016-07-01',
         'startDate2':'2016-07-01','endDate2':'2016-11-01',
         'month1':6,'month2':8}
zoom = 10
jet = 'black,blue,cyan,yellow,red'

if local:
# for local flask server
    ee.Initialize()
    msg = 'Choose a rectangular region'
    sentinel1 = 'sentinel1.html'
    sentinel2 = 'sentinel2.html'
    mad1 = 'mad.html'
    radcal1 = 'radcal.html'
    omnibus1 = 'omnibus.html'
else:
# for appengine deployment or development appserver
    import config
    msg = 'Choose a SMALL rectangular region'
    ee.Initialize(config.EE_CREDENTIALS, 'https://earthengine.googleapis.com')
    sentinel1 = 'sentinel1web.html'
    sentinel2 = 'sentinel2web.html'
    mad1 = 'madweb.html'
    radcal1 = 'radcalweb.html'
    omnibus1 = 'omnibusweb.html'    

app = Flask(__name__)

def iterate(image1,image2,niter,first):
#   simulated iteration of MAD for debugging          
#   result = iterate(image1,image2,niter,first)   
    for i in range(1,niter+1):
        result = ee.Dictionary(imad(i,first))
        allrhos = ee.List(result.get('allrhos'))
        chi2 = ee.Image(result.get('chi2'))
        MAD = ee.Image(result.get('MAD'))
        first = ee.Dictionary({'image':image1.addBands(image2),
                               'allrhos':allrhos,
                               'chi2':chi2,
                               'MAD':MAD})
    return result


#------------------
# helper functions
#------------------

def get_vv(image):   
    ''' get 'VV' band from sentinel-1 imageCollection and restore linear signal from db-values '''
    return image.select('VV').multiply(ee.Image.constant(math.log(10.0)/10.0)).exp()

def get_vh(image):   
    ''' get 'VH' band from sentinel-1 imageCollection and restore linear signal from db-values '''
    return image.select('VH').multiply(ee.Image.constant(math.log(10.0)/10.0)).exp()

def get_vvvh(image):   
    ''' get 'VV' and 'VH' bands from sentinel-1 imageCollection and restore linear signal from db-values '''
    return image.select('VV','VH').multiply(ee.Image.constant(math.log(10.0)/10.0)).exp()

def get_hh(image):   
    ''' get 'HH' band from sentinel-1 imageCollection and restore linear signal from db-values '''
    return image.select('HH').multiply(ee.Image.constant(math.log(10.0)/10.0)).exp()

def get_hv(image):   
    ''' get 'HV' band from sentinel-1 imageCollection and restore linear signal from db-values '''
    return image.select('HV').multiply(ee.Image.constant(math.log(10.0)/10.0)).exp()

def get_hhhv(image):   
    ''' get 'HH' and 'HV' bands from sentinel-1 imageCollection and restore linear signal from db-values '''
    return image.select('HH','HV').multiply(ee.Image.constant(math.log(10.0)/10.0)).exp()

def get_image(current,image):
    ''' accumulate a single image from a collection of images '''
    return ee.Image.cat(ee.Image(image),current)    
    
def clipList(current,prev):
    ''' clip a list of images '''
    imlist = ee.List(ee.Dictionary(prev).get('imlist'))
    rect = ee.Dictionary(prev).get('rect')    
    imlist = imlist.add(ee.Image(current).clip(rect))
    return ee.Dictionary({'imlist':imlist,'rect':rect})

def makefeature(data):
    ''' for exporting as CSV to Drive '''
    return ee.Feature(None, {'data': data})

#--------------------
# request handlers
#--------------------

@app.route('/')
def index():
    return app.send_static_file('index.html')
    
@app.route('/sentinel1.html', methods = ['GET', 'POST'])
def Sentinel1():    
    global glbls, msg, local, zoom
    if request.method == 'GET':
        return render_template(sentinel1, msg = msg,
                                          minLat = glbls['minLat'],
                                          minLon = glbls['minLon'],
                                          maxLat = glbls['maxLat'],
                                          maxLon = glbls['maxLon'],
                                          centerLon = glbls['centerLon'],
                                          centerLat = glbls['centerLat'],
                                          startDate = glbls['startDate'],
                                          endDate = glbls['endDate'],
                                          zoom = zoom)
    else:
        try: 
            startDate = request.form['startDate']  
            endDate = request.form['endDate']
            orbitpass = request.form['pass']
            polarization1 = request.form['polarization']
            relativeorbitnumber = request.form['relativeorbitnumber']
            if polarization1 == 'VV,VH':
                polarization = ['VV','VH']
            elif polarization1 == 'HH,HV':
                polarization = ['HH','HV']
            else:
                polarization = polarization1
            minLat = float(request.form['minLat'])
            minLon = float(request.form['minLon'])
            maxLat = float(request.form['maxLat'])
            maxLon = float(request.form['maxLon'])
            if request.form.has_key('export'):        
                export = request.form['export']
                gdexportname = request.form['exportname']
                gdexportscale = float(request.form['gdexportscale'])
            else:
                export = 'none'           
            if request.form.has_key('slanes'):        
                slanes = True  
            else:
                slanes = False  
            start = ee.Date(startDate)
            finish = ee.Date(endDate)    
            rect = ee.Geometry.Rectangle(minLon,minLat,maxLon,maxLat)     
            centerLon = (minLon + maxLon)/2.0
            centerLat = (minLat + maxLat)/2.0 
            ulPoint = ee.Geometry.Point([minLon,maxLat])   
            lrPoint = ee.Geometry.Point([maxLon,minLat])
            collection = ee.ImageCollection('COPERNICUS/S1_GRD') \
                        .filterBounds(ulPoint) \
                        .filterBounds(lrPoint) \
                        .filterDate(start, finish) \
                        .filter(ee.Filter.eq('transmitterReceiverPolarisation', polarization)) \
                        .filter(ee.Filter.eq('resolution_meters', 10)) \
                        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
                        .filter(ee.Filter.eq('orbitProperties_pass', orbitpass))                        
            if relativeorbitnumber != '':
                collection = collection.filter(ee.Filter.eq('relativeOrbitNumber_start', int(relativeorbitnumber))) 
            collection = collection.sort('system:time_start')                             
            systemids =  str(ee.List(collection.aggregate_array('system:id')).getInfo())                            
            acquisition_times = ee.List(collection.aggregate_array('system:time_start')).getInfo()                                           
            count = len(acquisition_times)
            if count==0:
                raise ValueError('No images found')   
            timestamplist = []
            for timestamp in acquisition_times:
                tmp = time.gmtime(int(timestamp)/1000)
                timestamplist.append(time.strftime('%c', tmp))
            timestamp = timestamplist[0]    
            timestamps = str(timestamplist)      
            relativeorbitnumbers = str(ee.List(collection.aggregate_array('relativeOrbitNumber_start')).getInfo())                                                       
            image = ee.Image(collection.first())                       
            systemid = image.get('system:id').getInfo()  
            projection = image.select(0).projection().getInfo()['crs']      
#          make into collection of VV, VH, HH, HV, HHHV or VVVH images and restore linear scale             
            if polarization1 == 'VV':
                pcollection = collection.map(get_vv)
            elif polarization1 == 'VH':
                pcollection = collection.map(get_vh)
            elif polarization1 == 'VV,VH':
                pcollection = collection.map(get_vvvh)
            elif polarization1 == 'HH':
                pcollection = collection.map(get_hh)
            elif polarization1 == 'HV':
                pcollection = collection.map(get_hv)
            elif polarization1 == 'HH,HV':
                pcollection = collection.map(get_hhhv)    
#          clipped image for display on map                
            if slanes:
#              just want max for shipping lanes
                outimage = pcollection.max().clip(rect)
                mapidclip = outimage.select(0).getMapId({'min': 0, 'max':1, 'opacity': 0.7})
                mapid = image.select(0).getMapId({'min': 0, 'max':1, 'opacity': 0.5})
                downloadtext = 'Download maximum intensity image'
                titletext = 'Sentinel-1 Maximum Intensity Image'
            else:
#              want the entire time series 
                mapid = image.select(0).getMapId({'min': 0, 'max':1, 'opacity': 0.5})
                image1clip = ee.Image(pcollection.first()).clip(rect)   
                mapidclip = image1clip.select(0).getMapId({'min': 0, 'max':1, 'opacity': 0.7})    
                downloadtext = 'Download image collection intersection'      
                titletext = 'Sentinel-1 Intensity Image'                                                      
#              clip the image collection and create a single multiband image      
                outimage = ee.Image(pcollection.iterate(get_image,image1clip))    
                                               
            if export == 'export':
#              export to Google Drive -------------------------
                gdexport = ee.batch.Export.image.toDrive(outimage,
                                                         description='driveExportTask', 
                                                         folder = 'EarthEngineImages',
                                                         fileNamePrefix=gdexportname,scale=gdexportscale,maxPixels=1e9)                
                
                gdexportid = str(gdexport.id)
                print >> sys.stderr, '****Exporting to Google Drive, task id: %s '%gdexportid
                gdexport.start() 
            else:
                gdexportid = 'none'
#              --------------------------------------------------                                        
            downloadpathclip =  outimage.getDownloadUrl({'scale':10})       
            
            glbls['minLat'] = minLat
            glbls['minLon'] = minLon
            glbls['maxLat'] = maxLat
            glbls['maxLon'] = maxLon  
            glbls['centerLon'] = centerLon
            glbls['centerLat'] = centerLat  
            glbls['startDate'] = startDate
            glbls['endDate'] = endDate
                                                                    
            return render_template('sentinel1out.html',
                                    mapid = mapid['mapid'],
                                    token = mapid['token'],
                                    mapidclip = mapidclip['mapid'], 
                                    tokenclip = mapidclip['token'], 
                                    centerLon = centerLon,
                                    centerLat = centerLat,
                                    zoom = zoom,
                                    downloadtext = downloadtext,
                                    titletext = titletext,
                                    downloadpathclip = downloadpathclip, 
                                    projection = projection,
                                    systemid = systemid,
                                    count = count,
                                    timestamp = timestamp,
                                    gdexportid = gdexportid,
                                    timestamps = timestamps,
                                    systemids = systemids,
                                    polarization = polarization1,
                                    relativeorbitnumbers = relativeorbitnumbers)  
        except Exception as e:
            return '<br />An error occurred in Sentinel1: %s<br /><a href="%s" name="return"> Return</a>'%(e,sentinel1) 
                  

@app.route('/sentinel2.html', methods = ['GET', 'POST'])
def Sentinel2():
    global glbls, msg, local, zoom
    if request.method == 'GET':
        return render_template(sentinel2, msg = msg,
                                          minLat = glbls['minLat'],
                                          minLon = glbls['minLon'],
                                          maxLat = glbls['maxLat'],
                                          maxLon = glbls['maxLon'],
                                          centerLon = glbls['centerLon'],
                                          centerLat = glbls['centerLat'],
                                          startDate = glbls['startDate'],
                                          endDate = glbls['endDate'],
                                          zoom = zoom)
    else:
        try:
            startDate = request.form['startDate']  
            endDate = request.form['endDate']
            minLat = float(request.form['minLat'])
            minLon = float(request.form['minLon'])
            maxLat = float(request.form['maxLat'])
            maxLon = float(request.form['maxLon'])
            if request.form.has_key('export'):        
                export = request.form['export']
                gdexportname = request.form['exportname'] 
                gdexportscale = float(request.form['gdexportscale']) 
            else:
                export = ' '          
            start = ee.Date(startDate)
            finish = ee.Date(endDate)           
            rect = ee.Geometry.Rectangle(minLon,minLat,maxLon,maxLat)     
            centerLon = (minLon + maxLon)/2.0
            centerLat = (minLat + maxLat)/2.0 
            ulPoint = ee.Geometry.Point([minLon,maxLat])   
            lrPoint = ee.Geometry.Point([maxLon,minLat]) 
            collection = ee.ImageCollection('COPERNICUS/S2') \
                        .filterBounds(ulPoint) \
                        .filterBounds(lrPoint) \
                        .filterDate(start, finish) \
                        .sort('CLOUD_COVERAGE_ASSESSMENT', True) 
            acquisition_times = ee.List(collection.aggregate_array('system:time_start')).getInfo()                         
            count = collection.toList(100).length().getInfo()    
            if count==0:
                raise ValueError('No images found')        
            sensingorbitnumbers = str(ee.List(collection.aggregate_array('SENSING_ORBIT_NUMBER')).getInfo())
            
            timestamplist = []
            for timestamp in acquisition_times:
                tmp = time.gmtime(int(timestamp)/1000)
                timestamplist.append(time.strftime('%c', tmp))
            timestamp = timestamplist[0]    
            timestamps = str(timestamplist)   
            
            image = ee.Image(collection.first())         
            imageclip = image.clip(rect)              
            systemid = image.get('system:id').getInfo()
            cloudcover = image.get('CLOUD_COVERAGE_ASSESSMENT').getInfo()
            projection = image.select('B2').projection().getInfo()['crs']
            downloadpath = image.getDownloadUrl({'scale':30,'crs':projection})    
            if export == 'export':
#              export to Google Drive --------------------------
                gdexport = ee.batch.Export.image.toDrive(imageclip.select('B2','B3','B4','B8'),
                                         description='driveExportTask', 
                                         folder = 'EarthEngineImages',
                                         fileNamePrefix=gdexportname,scale=gdexportscale,maxPixels=1e9) 
                
                
                gdexportid = str(gdexport.id)
                print >> sys.stderr, '****Exporting to Google Drive, task id: %s '%gdexportid
                gdexport.start() 
            else:
                gdexportid = 'none'
#              --------------------------------------------------                    
            downloadpathclip = imageclip.select('B2','B3','B4','B8').getDownloadUrl({'scale':10, 'crs':projection})
            rgb = image.select('B2','B3','B4')            
            rgbclip = imageclip.select('B2','B3','B4')                 
            mapid = rgb.getMapId({'min':0, 'max':2000, 'opacity': 0.6}) 
            mapidclip = rgbclip.getMapId({'min':0, 'max':3000, 'opacity': 1.0}) 
            
            glbls['minLat'] = minLat
            glbls['minLon'] = minLon
            glbls['maxLat'] = maxLat
            glbls['maxLon'] = maxLon  
            glbls['centerLon'] = centerLon
            glbls['centerLat'] = centerLat  
            glbls['startDate'] = startDate
            glbls['endDate'] = endDate 
                                 
            return render_template('sentinel2out.html',
                                    mapidclip = mapidclip['mapid'], 
                                    tokenclip = mapidclip['token'], 
                                    mapid = mapid['mapid'], 
                                    token = mapid['token'], 
                                    centerLon = centerLon,
                                    centerLat = centerLat,
                                    zoom = zoom,
                                    downloadtext = 'Download image intersection',
                                    downloadpath = downloadpath, 
                                    downloadpathclip = downloadpathclip, 
                                    systemid = systemid,
                                    cloudcover = cloudcover,
                                    projection = projection,
                                    count = count,
                                    sensingorbitnumbers = sensingorbitnumbers,
                                    timestamps = timestamps,
                                    timestamp = timestamp)  
        except Exception as e:
            return '<br />An error occurred in Sentinel2: %s<br /><a href="%s" name="return"> Return</a>'%(e,sentinel2)   
        
@app.route('/mad.html', methods = ['GET', 'POST'])
def Mad():
    global glbls, msg, local, zoom
    if request.method == 'GET':
        return render_template(mad1,msg = msg,
                                    minLat = glbls['minLat'],
                                    minLon = glbls['minLon'],
                                    maxLat = glbls['maxLat'],
                                    maxLon = glbls['maxLon'],
                                    centerLon = glbls['centerLon'],
                                    centerLat = glbls['centerLat'],
                                    startDate1 = glbls['startDate1'],
                                    endDate1 = glbls['endDate1'],
                                    startDate2 = glbls['startDate2'],
                                    endDate2 = glbls['endDate2'],
                                    zoom = zoom)
    else:
        try:
            hint = '(enable export to bypass this error)' 
            niter = int(request.form['iterations'])
            startDate1 = request.form['startDate1']
            endDate1 = request.form['endDate1']
            startDate2 = request.form['startDate2']
            endDate2 = request.form['endDate2']   
            minLat = float(request.form['minLat'])
            minLon = float(request.form['minLon'])
            maxLat = float(request.form['maxLat'])
            maxLon = float(request.form['maxLon'])
            collectionid = request.form['collectionid']
            if request.form.has_key('assexport'):        
                assexportscale = float(request.form['assexportscale'])
                assexportname = request.form['assexportname']
                assexport = request.form['assexport']
            else:
                assexport = 'none'
            if request.form.has_key('gdexport'):  
                gdexportscale = float(request.form['gdexportscale'])  
                gdexportname = request.form['gdexportname']    
                gdexport = request.form['gdexport']
            else:
                gdexport = 'none'                 
            rect = ee.Geometry.Rectangle(minLon,minLat,maxLon,maxLat)     
            centerLon = (minLon + maxLon)/2.0
            centerLat = (minLat + maxLat)/2.0 
            ulPoint = ee.Geometry.Point([minLon,maxLat])   
            lrPoint = ee.Geometry.Point([maxLon,minLat]) 
            cloudcover = 'CLOUD_COVER'
            if collectionid=='COPERNICUS/S2_10':
                collectionid = 'COPERNICUS/S2'
                bands = ['B2','B3','B4','B8']
                cloudcover = 'CLOUDY_PIXEL_PERCENTAGE'
            elif collectionid=='COPERNICUS/S2_20':   
                collectionid = 'COPERNICUS/S2'
                bands = ['B5','B6','B7','B8A','B11','B12']
                cloudcover = 'CLOUDY_PIXEL_PERCENTAGE'
            elif (collectionid=='LANDSAT/LC08/C01/T1_RT_TOA') or (collectionid=='LANDSAT/LC08/C01/T1_RT_TOA'):
                bands = ['B2','B3','B4','B5','B6','B7']               
            else:
                bands = ['B1','B2','B3','B4','B5','B7']                  
            collection = ee.ImageCollection(collectionid) \
                        .filterBounds(ulPoint) \
                        .filterBounds(lrPoint) \
                        .filterDate(ee.Date(startDate1), ee.Date(endDate1)) \
                        .sort(cloudcover, True) 
            count = collection.toList(100).length().getInfo()    
            if count==0:
                raise ValueError('No images found for first time interval')      
            image1 = ee.Image(collection.first()).select(bands)     
            timestamp1 = ee.Date(image1.get('system:time_start')).getInfo()
            timestamp1 = time.gmtime(int(timestamp1['value'])/1000)
            timestamp1 = time.strftime('%c', timestamp1)               
            systemid1 = image1.get('system:id').getInfo()
            cloudcover1 = image1.get(cloudcover).getInfo()
            collection = ee.ImageCollection(collectionid) \
                        .filterBounds(ulPoint) \
                        .filterBounds(lrPoint) \
                        .filterDate(ee.Date(startDate2), ee.Date(endDate2)) \
                        .sort(cloudcover, True) 
            count = collection.toList(100).length().getInfo()    
            if count==0:
                raise ValueError('No images found for second time interval')        
            image2 = ee.Image(collection.first()).clip(rect).select(bands)    
            timestamp2 = ee.Date(image2.get('system:time_start')).getInfo()
            timestamp2 = time.gmtime(int(timestamp2['value'])/1000)
            timestamp2 = time.strftime('%c', timestamp2) 
            systemid2 = image2.get('system:id').getInfo()  
            cloudcover2 = image2.get(cloudcover).getInfo()
            nbands = image1.bandNames().length().getInfo() 
            madnames = ['MAD'+str(i+1) for i in range(nbands)]
#          register
            image2 = image2.register(image1,60)                                                               
#          iMAD
            inputlist = ee.List.sequence(1,niter)
            first = ee.Dictionary({'done':ee.Number(0),
                                   'image':image1.addBands(image2).clip(rect),
                                   'allrhos': [ee.List.sequence(1,image1.bandNames().length())],
                                   'chi2':ee.Image.constant(0),
                                   'MAD':ee.Image.constant(0)})         
            print >> sys.stderr, '**** Iteration started ...'
            result = ee.Dictionary(inputlist.iterate(imad,first))                
            MAD = ee.Image(result.get('MAD')).rename(madnames)
            chi2 = ee.Image(result.get('chi2')).rename(['chi2'])
            allrhos = ee.Array(result.get('allrhos')).toList()                                   
#          radcal           
            ncmask = chi2cdf(chi2,nbands).lt(ee.Image.constant(0.05)).rename(['invarpix'])                     
            inputlist1 = ee.List.sequence(0,nbands-1)
            first = ee.Dictionary({'image':image1.addBands(image2),
                                   'ncmask':ncmask,
                                   'nbands':nbands,
                                   'rect':rect,
                                   'coeffs': ee.List([]),
                                   'normalized':ee.Image()})
            result = ee.Dictionary(inputlist1.iterate(radcal,first))          
            coeffs = ee.List(result.get('coeffs'))                    
            sel = ee.List.sequence(1,nbands)
            normalized = ee.Image(result.get ('normalized')).select(sel)                                             
            MAD = ee.Image.cat(MAD,chi2,ncmask,image1.clip(rect),image2.clip(rect),normalized.clip(rect))
            if assexport == 'assexport':
#              export metadata as CSV to Drive  
                ninvar = ee.String(ncmask.reduceRegion(ee.Reducer.sum().unweighted(),
                                                       scale=assexportscale,maxPixels= 1e9).toArray().project([0]))  
                metadata = ee.List(['IR-MAD: '+time.asctime(),
                                    timestamp1+': '+systemid1+' %CC: '+str(cloudcover1),
                                    timestamp2+': '+systemid2+' %CC: '+str(cloudcover2),
                                    'Asset Export Name: '+assexportname]) \
                                    .cat(['Canonical Correlations']) \
                                    .cat(allrhos) \
                                    .cat(['Radiometric Normalization, Invariant Pixels:']) \
                                    .cat([ninvar]) \
                                    .cat(['Slope, Intercept, R:']) \
                                    .cat(coeffs)      
                hint = '(batch export should complete)'             
                gdmetaexport = ee.batch.Export.table.toDrive(ee.FeatureCollection(metadata.map(makefeature)),
                             description='driveExportTask', 
                             folder = 'EarthEngineImages',
                             fileNamePrefix=assexportname.replace('/','-') )
                gdrhosexportid = str(gdmetaexport.id)
                print '****Exporting correlations as CSV to Drive, task id: %s '%gdrhosexportid            
                gdmetaexport.start()                  
#              export to Assets 
                assexport = ee.batch.Export.image.toAsset(MAD,
                                                          description='assetExportTask', 
                                                          assetId=assexportname,scale=assexportscale,maxPixels=1e9)
                assexportid = str(assexport.id)
                print '****Exporting MAD image to Assets, task id: %s '%assexportid
                assexport.start() 
            else:
                assexportid = 'none'                
            if gdexport == 'gdexport':              
#              export to Drive 
                hint = '(batch export should complete)'
                gdexport = ee.batch.Export.image.toDrive(MAD,description='driveExportTask', 
                                                         folder = 'EarthEngineImages',
                                                         fileNamePrefix=gdexportname,scale=gdexportscale,maxPixels=1e9)
                gdexportid = str(gdexport.id)
                print '****Exporting MAD image to Google Drive, task id: %s '%gdexportid
                gdexport.start() 
            else:
                gdexportid = 'none'    
                
            glbls['minLat'] = minLat
            glbls['minLon'] = minLon
            glbls['maxLat'] = maxLat
            glbls['maxLon'] = maxLon  
            glbls['centerLon'] = centerLon
            glbls['centerLat'] = centerLat   
            glbls['startDate1'] = startDate1
            glbls['endDate1'] = endDate1   
            glbls['startDate2'] = startDate2
            glbls['endDate2'] = endDate2     
                
            for rhos in allrhos.getInfo():
                print >> sys.stderr, rhos               
            mapid = chi2.getMapId({'min': 0, 'max':10000, 'opacity': 0.7})                             
            return render_template('madout.html',
                                    title = 'Chi Square Image',
                                    mapid = mapid['mapid'], 
                                    token = mapid['token'], 
                                    gdexportid = gdexportid,
                                    assexportid = assexportid,
                                    centerLon = centerLon,
                                    centerLat = centerLat,
                                    systemid1 = systemid1,
                                    systemid2 = systemid2,
                                    cloudcover1 = cloudcover1,
                                    cloudcover2 = cloudcover2,
                                    timestamp1 = timestamp1,
                                    timestamp2 = timestamp2)  
        except Exception as e:
            if isinstance(e,ValueError):
                return '<br />An error occurred in MAD: %s<br /><a href="%s" name="return"> Return</a>'%(e,mad1) 
            else:
                return render_template('madout.html',
                                        title = 'Error in MAD: %s '%e + hint,
                                        gdexportid = 'none',
                                        assexportid = 'none',
                                        centerLon = centerLon,
                                        centerLat = centerLat,
                                        systemid1 = systemid1,
                                        systemid2 = systemid2,
                                        cloudcover1 = cloudcover1,
                                        cloudcover2 = cloudcover2,
                                        timestamp1 = timestamp1,
                                        timestamp2 = timestamp2)                 

@app.route('/radcal.html', methods = ['GET', 'POST'])
def Radcal():       
    global glbls, msg, local, zoom
    if request.method == 'GET':
        return render_template(radcal1, msg = msg,
                                        minLat = glbls['minLat'],
                                        minLon = glbls['minLon'],
                                        maxLat = glbls['maxLat'],
                                        maxLon = glbls['maxLon'],
                                        centerLon = glbls['centerLon'],
                                        centerLat = glbls['centerLat'],
                                        startDate = glbls['startDate'],
                                        endDate = glbls['endDate'],
                                        month1 = glbls['month1'],
                                        month2 = glbls['month2'],
                                        zoom = zoom)
    else:
        try: 
            niter = int(request.form['niter'])
            startDate = request.form['startDate']
            endDate = request.form['endDate']
            month1 = int(request.form['month1'])
            month2 = int(request.form['month2'])
            maxcloudcover = float(request.form['maxcloudcover'])
            minLat = float(request.form['minLat'])
            minLon = float(request.form['minLon'])
            maxLat = float(request.form['maxLat'])
            maxLon = float(request.form['maxLon'])
            collectionid = request.form['collectionid']  
            refnumber = int(request.form['refnumber'])
            rect = ee.Geometry.Rectangle(minLon,minLat,maxLon,maxLat)     
            centerLon = (minLon + maxLon)/2.0
            centerLat = (minLat + maxLat)/2.0 
            ulPoint = ee.Geometry.Point([minLon,maxLat])   
            lrPoint = ee.Geometry.Point([maxLon,minLat]) 
            cloudcover = 'CLOUD_COVER'
            if collectionid=='COPERNICUS/S2_10':
                bandNames = ['B2','B3','B4','B8']
                collectionid = 'COPERNICUS/S2'
                cloudcover = 'CLOUDY_PIXEL_PERCENTAGE'
                displaymax = 5000
            elif collectionid =='COPERNICUS/S2_20':
                bandNames = ['B5','B6','B7','B8A','B11','B12']
                collectionid = 'COPERNICUS/S2'
                cloudcover = 'CLOUDY_PIXEL_PERCENTAGE' 
                displaymax = 5000
            elif collectionid=='LANDSAT/LC08/C01/T1_RT':
                bandNames = ['B2','B3','B4','B5','B6','B7'] 
                displaymax = 20000 
            elif collectionid=='LANDSAT/LC08/C01/T1_RT_TOA': 
                bandNames = ['B2','B3','B4','B5','B6','B7'] 
                displaymax = 1   
            elif collectionid=='LANDSAT/LE07/C01/T1_RT':
                bandNames = ['B1','B2','B3','B4','B5','B7']
                displaymax = 255
            elif collectionid=='LANDSAT/LE07/C01/T1_RT_TOA':
                bandNames = ['B1','B2','B3','B4','B5','B7']
                displaymax = 1
            elif collectionid=='LANDSAT/LT05/C01/T1':
                bandNames = ['B1','B2','B3','B4','B5','B7']
                displaymax = 255
            elif collectionid=='LANDSAT/LT05/C01/T1_TOA':
                bandNames = ['B1','B2','B3','B4','B5','B7']
                displaymax = 1   
            elif collectionid=='LANDSAT/LT4_L1T':
                bandNames = ['B1','B2','B3','B4','B5','B7']
                displaymax = 255
            elif collectionid=='LANDSAT/LT4_L1T_TOA':
                bandNames = ['B1','B2','B3','B4','B5','B7']
                displaymax = 1            
            if request.form.has_key('assexport'):        
                assexportscale = float(request.form['assexportscale'])
                assexportdir = request.form['assexportdir']
                assexport = request.form['assexport']
            else:
                assexport = 'none'
#          gather info               
            collection = ee.ImageCollection(collectionid) \
                           .select(bandNames) \
                           .filterBounds(ulPoint) \
                           .filterBounds(lrPoint) \
                           .filterDate(ee.Date(startDate),ee.Date(endDate)) \
                           .filter(ee.Filter.calendarRange(month1,month2,'month')) \
                           .filterMetadata(cloudcover,'less_than',maxcloudcover) \
                           .sort(cloudcover)                          
            count = collection.toList(100).length().getInfo()    
            if count<2:
                raise ValueError('Less than two images found for chosen time interval')   
            systemids =  ee.List(collection.aggregate_array('system:id')).getInfo() 
            acquisition_times = ee.List(collection.aggregate_array('system:time_start')).getInfo()  
            timestamplist = []
            for timestamp in acquisition_times:
                tmp = time.gmtime(int(timestamp)/1000)
                timestamplist.append(time.strftime('%x', tmp))   
            timestamps = str(timestamplist).replace("'",'')
            cloudcovers = ee.List(collection.aggregate_array(cloudcover)).getInfo()        
            imList = collection.toList(100)
            reference = ee.Image(imList.get(refnumber-1))
            refid = reference.get('system:id').getInfo()
            imList = imList.remove(reference)
            timestamp = ee.Date(reference.get('system:time_start')).getInfo()
            timestamp = time.gmtime(int(timestamp['value'])/1000)
            timestamp = time.strftime('%x', timestamp)                      
            referenceclip = reference.clip(rect)
            rgb = reference.select(1,2,3)            
            rgbclip = referenceclip.select(1,2,3)                 
            mapid = rgb.getMapId({'min':0, 'max':displaymax, 'opacity': 0.6}) 
            mapidclip = rgbclip.getMapId({'min':0, 'max':displaymax, 'opacity': 1.0}) 
            refcloudcover = reference.get(cloudcover).getInfo()
            msg1 = 'Batch export not submitted'
            if assexport != 'none':
#              batch normalization 
                log = ee.List(['RADCAL '+time.asctime(),'REFERENCE:', refid, 'TARGETS:'])            
                first = ee.Dictionary({'reference':reference,'rect':rect,'niter':niter,'log':log,'normalizedimages':ee.List([reference])})
                result = ee.Dictionary(imList.iterate(radcalbatch,first))
#              export log as featureCollection to Google Drive                
                log = ee.FeatureCollection(ee.List(result.get('log')).map(makefeature)) 
                gdmetaexport = ee.batch.Export.table.toDrive(log,
                             description='driveExportTask', 
                             folder = 'EarthEngineImages',
                             fileNamePrefix=assexportdir.replace('/','-') )           
                gdmetaexport.start()                  
#              export normalized images to Assets 
                imlist = ee.List(result.get('normalizedimages'))      
                for k in range(count):
                    if k == (refnumber-1):
                        suffix = '_REF'
                    else:
                        suffix = '_NORM'
                    assetId = assexportdir+systemids[k].replace('/','-')+suffix
                    assexport = ee.batch.Export.image.toAsset(imlist.get(k),
                                assetId = assetId,                 
                                description=assetId.replace('/','-'), 
                                scale=assexportscale,
                                maxPixels=1e9)
                    assexport.start()
                msg1 = 'Batch export submitted'         
#          return info            
            glbls['minLat'] = minLat
            glbls['minLon'] = minLon
            glbls['maxLat'] = maxLat
            glbls['maxLon'] = maxLon  
            glbls['centerLon'] = centerLon
            glbls['centerLat'] = centerLat 
            glbls['startDate'] = startDate
            glbls['endDate'] = endDate 
            glbls['month1'] = month1
            glbls['month2'] = month2
             
            return render_template('radcalout.html',
                                    title = 'Radiometric Normalization: '+msg1,
                                    count = count,
                                    mapid = mapid['mapid'], 
                                    token = mapid['token'], 
                                    mapidclip = mapidclip['mapid'], 
                                    tokenclip = mapidclip['token'], 
                                    refcloudcover = refcloudcover,
                                    timestamp = timestamp,
                                    timestamps =timestamps,
                                    systemids = str(systemids),
                                    cloudcovers = cloudcovers,
                                    centerLon = centerLon,
                                    centerLat = centerLat)
                              
        except Exception as e:
            return '<br />An error occurred in Radcal: %s<br /><a href="/radcal.html" name="return"> Return</a>'%e 


@app.route('/omnibus.html', methods = ['GET', 'POST'])
def Omnibus():       
    global glbls, msg, local, zoom
    if request.method == 'GET':
        return render_template(omnibus1, msg = msg,
                                        minLat = glbls['minLat'],
                                        minLon = glbls['minLon'],
                                        maxLat = glbls['maxLat'],
                                        maxLon = glbls['maxLon'],
                                        centerLon = glbls['centerLon'],
                                        centerLat = glbls['centerLat'],
                                        startDate = glbls['startDate'],
                                        endDate = glbls['endDate'],
                                        zoom = zoom)
    else:
        try: 
            hint = '(enable export to bypass this error)' 
            startDate = request.form['startDate']  
            endDate = request.form['endDate']  
            orbitpass = request.form['pass']
            display = request.form['display']
            polarization1 = request.form['polarization']
            relativeorbitnumber = request.form['relativeorbitnumber']
            if polarization1 == 'VV,VH':
                polarization = ['VV','VH']
            else:
                polarization = polarization1
            significance = float(request.form['significance'])                         
            minLat = float(request.form['minLat'])
            minLon = float(request.form['minLon'])
            maxLat = float(request.form['maxLat'])
            maxLon = float(request.form['maxLon'])        
            if request.form.has_key('assexport'):        
                assexportscale = float(request.form['assexportscale'])
                assexportname = request.form['assexportname']
                assexport = request.form['assexport']
            else:
                assexport = 'none'
            if request.form.has_key('gdexport'):  
                gdexportscale = float(request.form['gdexportscale'])  
                gdexportname = request.form['gdexportname']    
                gdexport = request.form['gdexport']
            else:
                gdexport = 'none'   
            if request.form.has_key('median'):        
                median = True
            else:
                median = False                           
            rect = ee.Geometry.Rectangle(minLon,minLat,maxLon,maxLat)     
            centerLon = (minLon + maxLon)/2.0
            centerLat = (minLat + maxLat)/2.0 
            ulPoint = ee.Geometry.Point([minLon,maxLat])   
            lrPoint = ee.Geometry.Point([maxLon,minLat])                
            collection = ee.ImageCollection('COPERNICUS/S1_GRD') \
                        .filterBounds(ulPoint) \
                        .filterBounds(lrPoint) \
                        .filterDate(ee.Date(startDate), ee.Date(endDate)) \
                        .filter(ee.Filter.eq('transmitterReceiverPolarisation', polarization)) \
                        .filter(ee.Filter.eq('resolution_meters', 10)) \
                        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
                        .filter(ee.Filter.eq('orbitProperties_pass', orbitpass)) 
            if relativeorbitnumber != '':
                collection = collection.filter(ee.Filter.eq('relativeOrbitNumber_start', int(relativeorbitnumber))) 
            collection = collection.sort('system:time_start')                                     
            acquisition_times = ee.List(collection.aggregate_array('system:time_start')).getInfo()                                           
            count = len(acquisition_times) 
            if count<2:
                raise ValueError('Less than 2 images found')   
            timestamplist = []
            for timestamp in acquisition_times:
                tmp = time.gmtime(int(timestamp)/1000)
                timestamplist.append(time.strftime('%x', tmp))  
#          make timestamps in TYYYYMMDD format            
            timestamplist = [x.replace('/','') for x in timestamplist]  
            timestamplist = ['T20'+x[4:]+x[0:4] for x in timestamplist]
#          in case of duplicates add running integer
            timestamplist1 = [timestamplist[i] + '_' + str(i+1) for i in range(len(timestamplist))]
#          remove duplicates
            timestamps = str(timestamplist1)
            timestamp = timestamplist1[0]                   
            relativeorbitnumbers = str(ee.List(collection.aggregate_array('relativeOrbitNumber_start')).getInfo())                                                                      
            image = ee.Image(collection.first())                       
            systemid = image.get('system:id').getInfo()   
            projection = image.select(0).projection().getInfo()['crs']
#          make into collection of VV, VH, HH, HV, HHHV or VVVH images and restore linear scale             
            if polarization1 == 'VV':
                pcollection = collection.map(get_vv)
            elif polarization1 == 'VH':
                pcollection = collection.map(get_vh)
            elif polarization1 == 'VV,VH':
                pcollection = collection.map(get_vvvh)
            elif polarization1 == 'HH':
                pcollection = collection.map(get_hh)
            elif polarization1 == 'HV':
                pcollection = collection.map(get_hv)
            elif polarization1 == 'HH,HV':
                pcollection = collection.map(get_hhhv)                      
#          get the list of images and clip to roi
            pList = pcollection.toList(count)   
            first = ee.Dictionary({'imlist':ee.List([]),'rect':rect}) 
            imList = ee.Dictionary(pList.iterate(clipList,first)).get('imlist')  
#          run the algorithm ------------------------------------------    
            result = ee.Dictionary(omnibus(imList,significance,median))
#          ------------------------------------------------------------            
            cmap = ee.Image(result.get('cmap')).byte()   
            smap = ee.Image(result.get('smap')).byte()
            fmap = ee.Image(result.get('fmap')).byte()  
            bmap = ee.Image(result.get('bmap')).byte()
            cmaps = ee.Image.cat(cmap,smap,fmap,bmap).rename(['cmap','smap','fmap']+timestamplist1[1:])  
            downloadpath = cmaps.getDownloadUrl({'scale':10})    
            
            assexportid = 'none'     
            gdexportid = 'none'        
            if assexport == 'assexport':
#              export metadata as CSV to Drive  
                metadata = ee.List(['SEQUENTIAL OMNIBUS: '+time.asctime(),
                        'Polarization: '+polarization1,            
                        'Timestamps: '+timestamps,
                        'Rel orbit numbers: '+relativeorbitnumbers,
                        'Asset export name: '+assexportname])   
                hint = '(batch export should complete)'             
                gdrhosexport = ee.batch.Export.table.toDrive(ee.FeatureCollection(metadata.map(makefeature)),
                             description='driveExportTask', 
                             folder = 'EarthEngineImages',
                             fileNamePrefix=assexportname.replace('/','-') )
                gdrhosexportid = str(gdrhosexport.id)
                print '****Exporting correlations as CSV to Drive, task id: %s '%gdrhosexportid            
                gdrhosexport.start()                
#              export to Assets 
                hint = '(batch export should complete)'
                assexport = ee.batch.Export.image.toAsset(cmaps,
                                                          description='assetExportTask', 
                                                          assetId=assexportname,scale=assexportscale,maxPixels=1e9)
                assexportid = str(assexport.id)
                print '****Exporting to Assets, task id: %s '%assexportid
                assexport.start() 
            
            if gdexport == 'gdexport':
#              export to Drive 
                hint = '(batch export should complete)'
                gdexport = ee.batch.Export.image.toDrive(cmaps,
                                                         description='driveExportTask', 
                                                         folder = 'EarthEngineImages',
                                                         fileNamePrefix=gdexportname,scale=gdexportscale,maxPixels=1e9)
                gdexportid = str(gdexport.id)
                print '****Exporting to Google Drive, task id: %s '%gdexportid
                gdexport.start() 
 
            if display=='fmap':                                                                                  
                mapid = fmap.getMapId({'min': 0, 'max': count/2,'palette': jet, 'opacity': 0.4}) 
                title = 'Sequential omnibus frequency map'
            elif display=='smap':
                mapid = smap.getMapId({'min': 0, 'max': count,'palette': jet, 'opacity': 0.4}) 
                title = 'Sequential omnibus first change map'
            else:
                mapid = cmap.getMapId({'min': 0, 'max': count,'palette': jet, 'opacity': 0.4})   
                title = 'Sequential omnibus last change map'    
                
            glbls['minLat'] = minLat
            glbls['minLon'] = minLon
            glbls['maxLat'] = maxLat
            glbls['maxLon'] = maxLon  
            glbls['centerLon'] = centerLon
            glbls['centerLat'] = centerLat
            glbls['startDate'] = startDate
            glbls['endDate'] = endDate                                                  
                
            return render_template('omnibusout.html',
                                    mapid = mapid['mapid'], 
                                    token = mapid['token'], 
                                    title = title,
                                    centerLon = centerLon,
                                    centerLat = centerLat,
                                    zoom = zoom,
                                    projection = projection,
                                    systemid = systemid,
                                    count = count,
                                    downloadpath = downloadpath,
                                    timestamp = timestamp,
                                    assexportid = assexportid,
                                    gdexportid = gdexportid,
                                    timestamps = timestamps,
                                    polarization = polarization1,
                                    relativeorbitnumbers = relativeorbitnumbers)                                          
        except Exception as e:
            if isinstance(e,ValueError):
                return '<br />An error occurred in Omnibus: %s<br /><a href="%s" name="return"> Return</a>'%(e,omnibus1)
            else:
                return render_template('omnibusout.html', 
                                        title = 'Error in omnibus: %s '%e + hint,
                                        centerLon = centerLon,
                                        centerLat = centerLat,
                                        zoom = zoom,
                                        projection = projection,
                                        systemid = systemid,
                                        count = count,
                                        assexportid = assexportid,
                                        gdexportid = gdexportid,
                                        timestamp = timestamp,
                                        timestamps = timestamps,
                                        polarization = polarization1,
                                        relativeorbitnumbers = relativeorbitnumbers)  
                                               
if __name__ == '__main__':   
    app.run(debug=True, host='0.0.0.0')
  