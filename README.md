# Change Detection with Google Earth Engine Imagery
A simple Flask web application for performing change detection tasks with 
<a href="https://developers.google.com/earth-engine/">Google Earth Engine</a> imagery *.    

The <a href="http://ms-image-analysis.appspot.com/static/index.html">AppEngine version</a> (web version) is for demonstration only and has very limited functionality.
Exporting results to Google Drive or to Earth Engine assets is in particular not possible. 

The local version runs in a Docker container serving the Flask web application on __localhost:5000__.
Assuming you have been authenticated (see below) to the Earth Engine, you can carry out the following tasks:

 1. Run the iMAD (iteratively re-weighted MAD) algorithm on LANDAT-5 TM bitemporal imagery. CCA is done on the client side 
 until Cholesky decomposition becomes available on the GEE API. This means that only small image subsets can be processed and iterations
 cannot exceed about 10. The code will later be extended to run LANDSAT-7, LANDSAT-8, ASTER 
 and Sentinel-2 optical/infrared imagery.
 
    <a href="http://www2.imm.dtu.dk/pubdb/views/publication_details.php?id=4695"> 
	A. A. Nielsen (2007). The Regularized Iteratively Reweighted MAD Method for Change Detection in Multi- and Hyperspectral Data.</a>

	<a href="http://www.amazon.com/Analysis-Classification-Change-Detection-Sensing/dp/1466570377/ref=dp_ob_title_bk"> M. J.Canty (2014). 
	Image Analysis, Classification and Change Detection in Remote Sensing, 3rd Ed., CRC Press 2014</a>; 
	
 2. Run the complex Wishart algorithm on polarimetric SAR bitemporal data (presently only Sentinel-1 dual pol, diagonal only, and single pol images).
 
	 <a href = "http://www2.imm.dtu.dk/pubdb/views/publication_details.php?id=1219"> 
	K. Conradsen et al. (2003). A test statistic in the complex Wishart distribution and its 
	application to change detection in polarimetric SAR data IEEE TGRS 41 (1) 4-19.</a>
	
	
 3. Run the (sequential) omnibus algorithm on polarimetric SAR multitemporal data (presently only Sentinel-1 dual pol, diagonal only, and single pol images).
 
	 <a href = "http://www2.imm.dtu.dk/pubdb/views/publication_details.php?id=6825"> 
	K. Conradsen et al. (2016). Determining the points of
	change in time series of polarimetric SAR data. IEEE TGRS 54 (5) 3007-3024.</a>

 3. Export imagery to your Earth Engine assets folder or to Google Drive for off-line local processing, 
 for example with <a href="http://mortcanty.github.io/SARDocker/"> SARDocker</a>.
 
\* Special thanks to Charles G. Morton for making available his implementation of the incomplete gamma function on the  GEE API.

### Installation and execution

 1. Install <a href="https://docs.docker.com/">Docker</a>
 
 2. In a command window execute the command
 
 		docker run -it -p 5000:5000 --name=ee mort/eedocker 
 		
 3. If the container is not found it will be automatically downloaded from Dockerhub and
 started. At the container prompt execute the command
 
 		earthengine authenticate
 	
 	and follow the instructions. You will have to copy the given URL and paste it into your local browser.
 	
 4. After successful authentication the credentials are saved to the container. Now run the command
 
 		./app.py
 	
 	and point your browser to 
 	
 		localhost:5000
 		
 	to start work.
 		
 5. When finished, hit 
 
 		Ctrl C 
 		
 	in the command window to stop the Flask application server and 
 
 		exit 
 		
 	to leave the container.
 
 6. Stop the container with
 
 		docker stop ee
 		
 7. Re-start and enter the container with
 
 		docker start -ai ee
 		
 8. Run the command
 
	    ./app.py
		
	to re-start the server.		
 		 		 		   		
 
 