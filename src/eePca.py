#!/usr/bin/env python
#  Name: eepca.py
import ee

def pca(image,scale=30,nbands=6,maxPixels=1e9): 
#  center the image
    bandNames=image.bandNames()
    meanDict=image.reduceRegion(ee.Reducer.mean(),
                  scale=scale,maxPixels=maxPixels)
    means=ee.Image.constant(meanDict.values(bandNames))
    centered=image.subtract(means) 
#  principal components analysis
    pcNames = ['pc'+str(i+1) for i in range(nbands)]
    centered=centered.toArray()
    covar=centered.reduceRegion(
            ee.Reducer.centeredCovariance(),
            scale=scale,maxPixels=maxPixels)
    covarArray=ee.Array(covar.get('array'))
    eigens=covarArray.eigen()
    lambdas=eigens.slice(1, 0, 1);
    eivs=eigens.slice(1, 1);
    centered=centered.toArray(1)   
    pcs=ee.Image(eivs).matrixMultiply(centered) \
                        .arrayProject([0]) \
                        .arrayFlatten([pcNames])
    return (pcs,lambdas)

if __name__ == '__main__':
    pass    
