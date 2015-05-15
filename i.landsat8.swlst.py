#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
 MODULE:       i.landsat8.swlst

 AUTHOR(S):    Nikos Alexandris <nik@nikosalexandris.net>
               Created on Wed Mar 18 10:00:53 2015
               First all-through execution: Tue May 12 21:50:42 EEST 2015

 PURPOSE:      A robust and practical Slit-Window (SW) algorithm estimating
               land surface temperature, from the Thermal Infra-Red Sensor
               (TIRS) aboard Landsat 8 with an accuracy of better than 1.0 K.

               The input parameters include:

               - the brightness temperatures (Ti and Tj) of the two adjacent
                 TIRS channels,

               - FROM-GLC land cover products and an emissivity look-up table,
                 which are a fraction of the FVC that can be estimated from the
                 red and near-infrared reflectance of the Operational Land
                 Imager (OLI).

               The algorithm's flowchart (Figure 3 in the paper [0]) is:

               +--------+   +--------------------------+
               |Landsat8+--->Cloud screen & calibration|
               +--------+   +---+--------+-------------+
                                |        |
                                |        |
                              +-v-+   +--v-+
                              |OLI|   |TIRS|
                              +-+-+   +--+-+
                                |        |
                                |        |
                             +--v-+   +--v-------------------+  +-------------+
                             |NDVI|   |Brightness temperature+-->MSWCVM method|
              +----------+   +--+-+   +--+-------------------+  +----------+--+
              |Land cover|      |        |                               |
              +----------+      |        |                               |
                      |       +-v-+   +--v-------------------+    +------v--+
                      |       |FVC|   |Split Window Algorithm|    |ColWatVap|
+---------------------v--+    +-+-+   +-------------------+--+    +------+--+
|Emissivity look|up table|      |                         |              |
+---------------------+--+      |                         |              |
                      |      +--v--------------------+    |    +---------v--+
                      +------>Pixel emissivity ei, ej+--> | <--+Coefficients|
                             +-----------------------+    |    +------------+
                                                          |
                                                          |
                                          +---------------v--+
                                          |LST and emissivity|
                                          +------------------+

               Sources:

               [0] Du, Chen; Ren, Huazhong; Qin, Qiming; Meng, Jinjie;
               Zhao, Shaohua. 2015. "A Practical Split-Window Algorithm
               for Estimating Land Surface Temperature from Landsat 8 Data."
               Remote Sens. 7, no. 1: 647-665.
               <http://www.mdpi.com/2072-4292/7/1/647/htm#sthash.ba1pt9hj.dpuf>

               [1] Huazhong Ren, Chen Du, Qiming Qin, Rongyuan Liu,
               Jinjie Meng, and Jing Li. "Atmospheric Water Vapor Retrieval
               from Landsat 8 and Its Validation." 3045–3048. IEEE, 2014.


               Details

               A new refinement of the generalized split-window algorithm
               proposed by Wan (2014) [19] is added with a quadratic term of
               the difference amongst the brightness temperatures (Ti, Tj) of
               the adjacent thermal infrared channels, which can be expressed
               as (equation 2 in the paper [0])

               LST = b0 +
                    [b1 + b2 * (1−ε)/ε + b3 * (Δε/ε2)] * (Ti+T)/j2 +
                    [b4 + b5 * (1−ε)/ε + b6 * (Δε/ε2)] * (Ti−Tj)/2 +
                     b7 * (Ti−Tj)^2

               where:

               - Ti and Tj are Top of Atmosphere brightness temperatures
               measured in channels i (~11.0 μm) and j (~12.0 µm),
               respectively;
                 - from
            <http://landsat.usgs.gov/band_designations_landsat_satellites.php>:
                   - Band 10, Thermal Infrared (TIRS) 1, 10.60-11.19, 100*(30)
                   - Band 11, Thermal Infrared (TIRS) 2, 11.50-12.51, 100*(30)

               - ε is the average emissivity of the two channels (i.e., ε = 0.5
               [εi + εj]),

               - Δε is the channel emissivity difference (i.e., Δε = εi − εj);

               - bk (k = 0,1,...7) are the algorithm coefficients derived in
               the following simulated dataset.

               [...]

               In the above equations,

                   - dk (k = 0, 1...6) and ek (k = 1, 2, 3, 4) are the
                   algorithm coefficients;

                   - w is the CWV;

                   - ε and ∆ε are the average emissivity and emissivity
                   difference of two adjacent thermal channels, respectively,
                   which are similar to Equation (2);

                   - and fk (k = 0 and 1) is related to the influence of the
                   atmospheric transmittance and emissivity, i.e., f k =
                   f(εi,εj,τ i ,τj).

                Note that the algorithm (Equation (6a)) proposed by
                Jiménez-Muñoz et al. added CWV directly to estimate LST.

                Rozenstein et al. used CWV to estimate the atmospheric
                transmittance (τi, τj) and optimize retrieval accuracy
                explicitly.

                Therefore, if the atmospheric CWV is unknown or cannot be
                obtained successfully, neither of the two algorithms in
                Equations (6a) and (6b) will work. By contrast, although our
                algorithm also needs CWV to determine the coefficients, this
                algorithm still works for unknown CWVs because the coefficients
                are obtained regardless of the CWV, as shown in Table 1.

 COPYRIGHT:    (C) 2015 by the GRASS Development Team

               This program is free software under the GNU General Public
               License (>=v2). Read the file COPYING that comes with GRASS
               for details.

"""

#%Module
#%  description: Practical split-window algorithm estimating Land Surface Temperature from Landsat 8 OLI/TIRS imagery (Du, Chen; Ren, Huazhong; Qin, Qiming; Meng, Jinjie; Zhao, Shaohua. 2015)
#%  keywords: imagery
#%  keywords: split window
#%  keywords: land surface temperature
#%  keywords: lst
#%  keywords: landsat8
#%End

#%flag
#%  key: i
#%  description: Print out model equations, citation
#%end

#%flag
#%  key: k
#%  description: Keep current computational region settings
#%end

#%flag
#% key: c
#% description: Apply Celsius colortable to output LST map
#%end

#%option
#% key: mtl
#% key_desc: mtl file
#% description: Landsat8 metadata file (MTL)
#% required: no
#%end

#%option G_OPT_R_BASENAME_INPUT
#% key: prefix
#% key_desc: string
#% type: string
#% label: OLI/TIRS band names prefix
#% description: Prefix of Landsat8 OLI/TIRS band names
#% required: no
#%end

##%rules
##% collective: prefix, mtl
##%end

#%option G_OPT_R_INPUT
#% key: b10
#% key_desc: Band 10
#% description: TIRS 10 (10.60 - 11.19 microns)
#% required : no
#%end

#%rules
#% requires_all: b10, mtl
#%end

#%option G_OPT_R_INPUT
#% key: b11
#% key_desc: Band 11
#% description: TIRS 11 (11.50 - 12.51 microns)
#% required : no
#%end

#%rules
#% requires_all: b11, mtl
#%end

#%option G_OPT_R_INPUT
#% key: t10
#% key_desc: Brightness Temperature 10
#% description: Brightness temperature (K) from band 10 | Overrides 'b10'
#% required : no
#%end

#%option G_OPT_R_INPUT
#% key: t11
#% key_desc: Brightness Temperature 11
#% description: Brightness temperature (K) from band 11 | Overrides 'b11'
#% required : no
#%end

#%rules
#% requires: b10, b11, t11
#%end

#%rules
#% requires: b11, b10, t10
#%end

#%rules
#% requires: t10, t11, b11
#%end

#%rules
#% requires: t11, t10, b10
#%end

#%rules
#% exclusive: b10, t10
#%end

#%rules
#% exclusive: b11, t11
#%end

#%option G_OPT_R_INPUT
#% key: qab
#% key_desc: QA band
#% description: Landsat 8 quality assessment band
#% required : no
#%end

#%option
#% key: qapixel
#% key_desc: qa pixel value
#% description: Quality assessment pixel value which to build a mask | Source: <http://landsat.usgs.gov/L8QualityAssessmentBand.php>.
#% answer: 61440
#% required: no
#% multiple: yes
#%end

#%rules
#% excludes: prefix, b10, b11, qab
#%end

#%option G_OPT_R_INPUT
#% key: clouds
#% key_desc: Clouds MASK
#% description: A raster map applied as an inverted MASK | Overrides 'qab'
#% required : no
#%end

#%rules
#% exclusive: qab, clouds
#%end

#%option G_OPT_R_INPUT
#% key: average_emissivity
#% key_desc: Average emissivity
#% description: Average emissivity map for Landsat8 TIRS channels 10 and 11 | Optional, expert use
#% required : no
#%end

#%option G_OPT_R_INPUT
#% key: delta_emissivity
#% key_desc: Delta Emissivity
#% description: Emissivity difference map for Landsat8 TIRS channels 10 and 11 | Optional, expert use
#% required : no
#%end

#%option G_OPT_R_INPUT
#% key: landcover
#% key_desc: FROM-GLC map name
#% description: FROM-GLC products covering the Landsat8 scene under processing. Source <http://data.ess.tsinghua.edu.cn/>.
#% required : no
#%end

#%option
#% key: emissivity_class
#% key_desc: emissivity class
#% description: Retrieve average emissivities only for a single land cover class (case sensitive) | Test or expert use
#% options: Cropland, Forest, Grasslands, Shrublands, Wetlands, Waterbodies, Tundra, Impervious, Barren, Snow, Random
#% required : no
#%end

#%rules
#% required: landcover, emissivity_class
#% exclusive: landcover, emissivity_class
#%end

#%option G_OPT_R_OUTPUT
#% key: lst
#% key_desc: lst output
#% description: Name for output Land Surface Temperature map
#% required: yes
#% answer: lst
#%end

#%option
#% key: window
#% key_desc: cwv window size
#% description: Odd number n sizing an n^2 spatial window for column water vapor retrieval | Details in the manual 
#% answer: 3
#% required: yes
#%end

#%option G_OPT_R_OUTPUT
#% key: cwv
#% key_desc: cwv output
#% description: Name for output Column Water Vapor map | Optional
#% required: no
#%end

# required librairies
import os
import sys
sys.path.insert(1, os.path.join(os.path.dirname(sys.path[0]),
                                'etc', 'i.landsat8.swlst'))

import atexit
import grass.script as grass
# from grass.exceptions import CalledModuleError
from grass.pygrass.modules.shortcuts import general as g
from grass.pygrass.modules.shortcuts import raster as r
# from grass.pygrass.raster.abstract import Info

from split_window_lst import *
from landsat8_mtl import Landsat8_MTL

if "GISBASE" not in os.environ:
    print "You must be in GRASS GIS to run this program."
    sys.exit(1)

# globals
DUMMY_MAPCALC_STRING_RADIANCE = 'Radiance'
DUMMY_MAPCALC_STRING_DN = 'DigitalNumber'
DUMMY_MAPCALC_STRING_T10 = 'Input_T10'
DUMMY_MAPCALC_STRING_T11 = 'Input_T11'
DUMMY_MAPCALC_STRING_AVG_LSE = 'Input_AVG_LSE'
DUMMY_MAPCALC_STRING_DELTA_LSE = 'Input_DELTA_LSE'
DUMMY_MAPCALC_STRING_FROM_GLC = 'Input_FROMGLC'
DUMMY_MAPCALC_STRING_CWV = 'Input_CWV'
DUMMY_Ti_MEAN = 'Mean_Ti'
DUMMY_Tj_MEAN = 'Mean_Tj'
DUMMY_Rji = 'Ratio_ji'


# helper functions
def cleanup():
    """
    Clean up temporary maps
    """
    grass.run_command('g.remove', flags='f', type="rast",
                      pattern='tmp.{pid}*'.format(pid=os.getpid()), quiet=True)


def run(cmd, **kwargs):
    """
    Pass required arguments to grass commands (?)
    """
    grass.run_command(cmd, quiet=True, **kwargs)


def save_map(mapname):
    """
    Helper function to save some in-between maps, assisting in debugging
    """
    # run('r.info', map=mapname, flags='r')
    run('g.copy', raster=(mapname, 'DebuggingMap'))


def random_digital_numbers(count=2):
    """
    Return a user-requested amount of random Digital Number values for testing
    purposes ranging in 12-bit
    """
    digital_numbers = []

    for dn in range(0, count):
        digital_numbers.append(random.randint(1, 2**12))

    if count == 1:
        return digital_numbers[0]

    return digital_numbers


def random_column_water_vapor_subrange():
    """
    Helper function, while coding and testing, returning a random column water
    vapour key to assist in testing the module.
    """
    cwvkey = random.choice(COLUMN_WATER_VAPOUR.keys())
    # COLUMN_WATER_VAPOUR[cwvkey].subrange
    # COLUMN_WATER_VAPOUR[cwvkey].rmse
    return cwvkey


def random_column_water_vapor_value():
    """
    Helper function, while coding and testing, returning a random value for
    column water vapor.
    """
    return random.uniform(0.0, 6.3)


def extract_number_from_string(string):
    """
    Extract the (integer) number from a string. Meand to be used with band
    names. For example:

    print extract_number_from_string('B10')

    will return

    10
    """
    import re
    return str(re.findall(r"[+-]? *(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?",
               string)[-1])


def get_metadata(mtl_filename, bandnumber):
    """
    Retrieve metadata of interest for given band.
    """
    metadata = Landsat8_MTL(mtl_filename)
    msg = "Scene ID is:" + str(metadata.scene_id)
    grass.verbose(msg)

    return metadata


def digital_numbers_to_radiance(outname, band, radiance_expression):
    """
    Convert Digital Numbers to TOA Radiance. For details, see in Landsat8
    class.
    """
    msg = "\n|i Rescaling {band} digital numbers to spectral radiance "
    msg = msg.format(band=band)

    if info:
        msg += '| Expression: '
        msg += radiance_expression
    g.message(msg)
    radiance_expression = replace_dummies(radiance_expression,
                                          instring=DUMMY_MAPCALC_STRING_DN,
                                          outstring=band)
    radiance_equation = equation.format(result=outname,
                                        expression=radiance_expression)

    grass.mapcalc(radiance_equation, overwrite=True)

    if info:
        run('r.info', map=outname, flags='r')

    del(radiance_expression)
    del(radiance_equation)


def radiance_to_brightness_temperature(outname, radiance, temperature_expression):
    """
    Convert Spectral Radiance to At-Satellite Brightness Temperature. For
    details see Landsat8 class.
    """
    temperature_expression = replace_dummies(temperature_expression,
                                             instring=DUMMY_MAPCALC_STRING_RADIANCE,
                                             outstring=radiance)

    msg = "\n|i Converting spectral radiance to at-Satellite Temperature "
    if info:
        msg += "| Expression: " + str(temperature_expression)
    g.message(msg)

    temperature_equation = equation.format(result=outname,
                                           expression=temperature_expression)

    grass.mapcalc(temperature_equation, overwrite=True)

    if info:
        run('r.info', map=outname, flags='r')

    del(temperature_expression)
    del(temperature_equation)


def tirs_to_at_satellite_temperature(tirs_1x, mtl_file):
    """
    Helper function to convert TIRS bands 10 or 11 in to at-satellite
    temperatures.

    This function uses the pre-defined functions:

    - extract_number_from_string()
    - digital_numbers_to_radiance()
    - radiance_to_brightness_temperature()

    The inputs are:

    - a name for the input tirs band (10 or 11)
    - a Landsat8 MTL file

    The output is a temporary at-Satellite Temperature map.
    """
    # which band number and MTL file
    band_number = extract_number_from_string(tirs_1x)
    tmp_radiance = tmp + '.radiance' + '.' + band_number
    tmp_brightness_temperature = tmp + '.brightness_temperature' + '.' + \
        band_number
    landsat8 = Landsat8_MTL(mtl_file)

    # rescale DNs to spectral radiance
    radiance_expression = landsat8.toar_radiance(band_number)
    digital_numbers_to_radiance(tmp_radiance, tirs_1x, radiance_expression)

    # convert spectral radiance to at-satellite temperature
    temperature_expression = landsat8.radiance_to_temperature(band_number)
    radiance_to_brightness_temperature(tmp_brightness_temperature,
                                       tmp_radiance,
                                       temperature_expression)

    del(radiance_expression)
    del(temperature_expression)

    return tmp_brightness_temperature


def mask_clouds(qa_band, qa_pixel):
    """
    ToDo:

    - a better, independent mechanism for QA. --> see also Landsat8 class.
    - support for multiple qa_pixel values (eg. input as a list of values)

    Create and apply a cloud mask based on the Quality Assessment Band
    (BQA.) Source: <http://landsat.usgs.gov/L8QualityAssessmentBand.php

    See also:
    http://courses.neteler.org/processing-landsat8-data-in-grass-gis-7/#Applying_the_Landsat_8_Quality_Assessment_%28QA%29_Band
    """
    msg = ('\n|i Masking for pixel values <{qap}> '
           'in the Quality Assessment band.'.format(qap=qa_pixel))
    g.message(msg)

    tmp_cloudmask = tmp + '.cloudmask'
    qabits_expression = 'if({band} == {pixel}, 1, null())'.format(band=qa_band,
                                                                  pixel=qa_pixel)

    cloud_masking_equation = equation.format(result=tmp_cloudmask,
                                             expression=qabits_expression)
    grass.mapcalc(cloud_masking_equation)

    r.mask(raster=tmp_cloudmask, flags='i', overwrite=True)

    # save for debuging
    #save_map(tmp_cloudmask)

    del(qabits_expression)
    del(cloud_masking_equation)


def replace_dummies(string, *args, **kwargs):
    """
    Replace DUMMY_MAPCALC_STRINGS (see SplitWindowLST class for it)
    with input maps ti, tj (here: t10, t11).

    - in_ti and in_tj are the "input" strings, for example:
    in_ti = 'Input_T10'  and  in_tj = 'Input_T11'

    - out_ti and out_tj are the output strings which correspond to map
    names, user-fed or in-between temporary maps, for example:
    out_ti = t10  and  out_tj = t11

    or

    out_ti = tmp_ti_mean  and  out_tj = tmp_ti_mean

    (Idea sourced from: <http://stackoverflow.com/a/9479972/1172302>)
    """
    inout = set(['instring', 'outstring'])
    # if inout.issubset(set(kwargs)):  # alternative
    if inout == set(kwargs):
        instring = kwargs.get('instring', 'None')
        outstring = kwargs.get('outstring', 'None')

        # end comma important!
        replacements = (str(instring), str(outstring)),

    in_tij_out = set(['in_ti', 'out_ti', 'in_tj', 'out_tj'])

    if in_tij_out == set(kwargs):
        in_ti = kwargs.get('in_ti', 'None')
        out_ti = kwargs.get('out_ti', 'None')
        in_tj = kwargs.get('in_tj', 'None')
        out_tj = kwargs.get('out_tj', 'None')

        replacements = (in_ti, str(out_ti)), (in_tj, str(out_tj))

    in_tijm_out = set(['in_ti', 'out_ti', 'in_tj', 'out_tj',
                       'in_tim', 'out_tim', 'in_tjm', 'out_tjm'])

    if in_tijm_out == set(kwargs):
        in_ti = kwargs.get('in_ti', 'None')
        out_ti = kwargs.get('out_ti', 'None')
        in_tj = kwargs.get('in_tj', 'None')
        out_tj = kwargs.get('out_tj', 'None')
        in_tim = kwargs.get('in_tim', 'None')
        out_tim = kwargs.get('out_tim', 'None')
        in_tjm = kwargs.get('in_tjm', 'None')
        out_tjm = kwargs.get('out_tjm', 'None')

        replacements = (in_ti, str(out_ti)), (in_tj, str(out_tj)), \
                       (in_tim, str(out_tim)), (in_tjm, str(out_tjm))

    in_cwv_out = set(['in_ti', 'out_ti', 'in_tj', 'out_tj', 'in_cwv',
                      'out_cwv'])

    if in_cwv_out == set(kwargs):
        in_cwv = kwargs.get('in_cwv', 'None')
        out_cwv = kwargs.get('out_cwv', 'None')
        in_ti = kwargs.get('in_ti', 'None')
        out_ti = kwargs.get('out_ti', 'None')
        in_tj = kwargs.get('in_tj', 'None')
        out_tj = kwargs.get('out_tj', 'None')

        replacements = (in_ti, str(out_ti)), (in_tj, str(out_tj)), \
                       (in_cwv, str(out_cwv))

    in_lst_out = set(['in_ti', 'out_ti', 'in_tj', 'out_tj', 'in_cwv',
                      'out_cwv', 'in_avg_lse', 'out_avg_lse', 'in_delta_lse',
                      'out_delta_lse'])

    if in_lst_out == set(kwargs):
        in_cwv = kwargs.get('in_cwv', 'None')
        out_cwv = kwargs.get('out_cwv', 'None')
        in_ti = kwargs.get('in_ti', 'None')
        out_ti = kwargs.get('out_ti', 'None')
        in_tj = kwargs.get('in_tj', 'None')
        out_tj = kwargs.get('out_tj', 'None')
        in_avg_lse = kwargs.get('in_avg_lse', 'None')
        out_avg_lse = kwargs.get('out_avg_lse', 'None')
        in_delta_lse = kwargs.get('in_delta_lse', 'None')
        out_delta_lse = kwargs.get('out_delta_lse', 'None')

        replacements = (in_ti, str(out_ti)), \
                       (in_tj, str(out_tj)), \
                       (in_cwv, str(out_cwv)), \
                       (in_avg_lse, str(out_avg_lse)), \
                       (in_delta_lse, str(out_delta_lse))

    return reduce(lambda alpha, omega: alpha.replace(*omega),
                  replacements, string)


def determine_average_emissivity(outname, landcover_map, avg_lse_expression):
    """
    """
    msg = ('\n|i Determining average land surface emissivity based on a '
           'look-up table ')
    if info:
        msg += ('| Expression:\n\n {exp}')
        msg = msg.format(exp=avg_lse_expression)
    g.message(msg)

    avg_lse_expression = replace_dummies(avg_lse_expression,
                                         instring=DUMMY_MAPCALC_STRING_FROM_GLC,
                                         outstring=landcover_map)

    avg_lse_equation = equation.format(result=outname,
                                       expression=avg_lse_expression)

    grass.mapcalc(avg_lse_equation, overwrite=True)

    if info:
        run('r.info', map=outname, flags='r')

    # uncomment below to save for testing!
    #save_map(outname)

    del(avg_lse_expression)
    del(avg_lse_equation)


def determine_delta_emissivity(outname, landcover_map, delta_lse_expression):
    """
    """
    msg = ('\n|i Determining delta land surface emissivity based on a '
           'look-up table ')
    if info:
        msg += ('| Expression:\n\n {exp}')
        msg = msg.format(exp=delta_lse_expression)
    g.message(msg)

    delta_lse_expression = replace_dummies(delta_lse_expression,
                                           instring=DUMMY_MAPCALC_STRING_FROM_GLC,
                                           outstring=landcover_map)

    delta_lse_equation = equation.format(result=outname,
                                         expression=delta_lse_expression)

    grass.mapcalc(delta_lse_equation, overwrite=True)

    if info:
        run('r.info', map=outname, flags='r')

    # uncomment below to save for testing!
    #save_map(outname)

    del(delta_lse_expression)
    del(delta_lse_equation)


def get_cwv_window_means(outname, t1x, t1x_mean_expression):
    """

    ***
    This function is NOT used.  It was part of an initial step-by-step approach,
    while coding and testing.  Kept for future plans!?
    ***

    Get window means for T1x
    """
    msg = ('\n |i Deriving window means from {Tx} ')
    msg += ('using the expression:\n {exp}')
    msg = msg.format(Tx=t1x, exp=t1x_mean_expression)
    g.message(msg)

    tx_mean_equation = equation.format(result=outname,
                                       expression=t1x_mean_expression)
    grass.mapcalc(tx_mean_equation, overwrite=True)

    if info:
        run('r.info', map=outname, flags='r')

    del(t1x_mean_expression)
    del(tx_mean_equation)


def estimate_ratio_ji(outname, tmp_ti_mean, tmp_tj_mean, ratio_expression):
    """

    ***
    This function is NOT used.  It was part of an initial step-by-step approach,
    while coding and testing.  Kept for future plans!?
    ***

    Estimate Ratio ji for the Column Water Vapor retrieval equation.
    """
    msg = '\n |i Estimating ratio Rji...'
    msg += '\n' + ratio_expression
    g.message(msg)

    ratio_expression = replace_dummies(ratio_expression,
                                       in_ti=DUMMY_Ti_MEAN, out_ti=tmp_ti_mean,
                                       in_tj=DUMMY_Tj_MEAN, out_tj=tmp_tj_mean)

    ratio_equation = equation.format(result=outname,
                                     expression=ratio_expression)

    grass.mapcalc(ratio_equation, overwrite=True)

    if info:
        run('r.info', map=outname, flags='r')


def estimate_column_water_vapor(outname, ratio, cwv_expression):
    """

    ***
    This function is NOT used.  It was part of an initial step-by-step approach,
    while coding and testing.  Kept for future plans!?
    ***

    """
    msg = "\n|i Estimating atmospheric column water vapor "
    msg += '| Mapcalc expression: '
    msg += cwv_expression
    g.message(msg)

    cwv_expression = replace_dummies(cwv_expression,
                                     instring=DUMMY_Rji,
                                     outstring=ratio)

    cwv_equation = equation.format(result=outname, expression=cwv_expression)

    grass.mapcalc(cwv_equation, overwrite=True)

    if info:
        run('r.info', map=outname, flags='r')

    # save Column Water Vapor map?
    if cwv_output:
        run('g.copy', raster=(outname, cwv_output))

    # uncomment below to save for testing!
    # save_map(outname)


def estimate_cwv_big_expression(outname, t10, t11, cwv_expression):
    """
    Derive a column water vapor map using a single mapcalc expression based on
    eval.

            *** To Do: evaluate -- does it work correctly? *** !
    """
    msg = "\n|i Estimating atmospheric column water vapor "
    if info:
        msg += '| Expression:\n'
    g.message(msg)

    if info:
        msg = replace_dummies(cwv_expression,
                              in_ti=t10, out_ti='T10',
                              in_tj=t11, out_tj='T11')
        msg += '\n'
        print msg

    cwv_equation = equation.format(result=outname, expression=cwv_expression)
    grass.mapcalc(cwv_equation, overwrite=True)

    if info:
        run('r.info', map=outname, flags='r')

    # save Column Water Vapor map?
    if cwv_output:

        # strings for metadata
        history_cwv = 'Column Water Vapor model: '
        history_cwv += 'Add info here'
        title_cwv = 'Column Water Vapor (?)'
        description_cwv = ('Split-Window LST')
        units_cwv = 'FixMe'
        source1_cwv = 'Add here'
        source2_cwv = 'Add here'

        # history entry
        run("r.support", map=outname, title=title_cwv,
            units=units_cwv, description=description_cwv,
            source1=source1_cwv, source2=source2_cwv,
            history=history_cwv)

        run('g.copy', raster=(outname, cwv_output))

    del(cwv_expression)
    del(cwv_equation)


def estimate_lst(outname, t10, t11, avg_lse_map, delta_lse_map, cwv_map, lst_expression):
    """
    Produce a Land Surface Temperature map based on a mapcalc expression
    returned from a SplitWindowLST object.

    Inputs are:

    - brightness temperature maps t10, t11
    - column water vapor map
    - a temporary filename
    - a valid mapcalc expression
    """
    msg = '\n|i Estimating land surface temperature '
    if info:
        msg += "| Expression:\n"
    g.message(msg)

    if info:
        msg = lst_expression
        msg += '\n'
        print msg

    # replace the "dummy" string...
    if landcover_map:
        split_window_expression = replace_dummies(lst_expression,
                                                  in_avg_lse=DUMMY_MAPCALC_STRING_AVG_LSE,
                                                  out_avg_lse=avg_lse_map,
                                                  in_delta_lse=DUMMY_MAPCALC_STRING_DELTA_LSE,
                                                  out_delta_lse=delta_lse_map,
                                                  in_cwv=DUMMY_MAPCALC_STRING_CWV,
                                                  out_cwv=cwv_map,
                                                  in_ti=DUMMY_MAPCALC_STRING_T10,
                                                  out_ti=t10,
                                                  in_tj=DUMMY_MAPCALC_STRING_T11,
                                                  out_tj=t11)
    elif emissivity_class:
        split_window_expression = replace_dummies(lst_expression,
                                                  in_cwv=DUMMY_MAPCALC_STRING_CWV,
                                                  out_cwv=cwv_map,
                                                  in_ti=DUMMY_MAPCALC_STRING_T10,
                                                  out_ti=t10,
                                                  in_tj=DUMMY_MAPCALC_STRING_T11,
                                                  out_tj=t11)

    split_window_equation = equation.format(result=outname,
                                            expression=split_window_expression)

    grass.mapcalc(split_window_equation, overwrite=True)

    if info:
        run('r.info', map=outname, flags='r')

    del(split_window_expression)
    del(split_window_equation)


def main():
    """
    Main program
    """

    # prefix for Temporary files
    global tmp
    tmpfile = grass.tempfile()  # replace with os.getpid?
    tmp = "tmp." + grass.basename(tmpfile)  # use its basename

    # Temporary filenames
    # tmp_ti_mean = tmp + '.ti_mean'  # for cwv
    # tmp_tj_mean = tmp + '.tj_mean'  # for cwv
    # tmp_ratio = tmp + '.ratio'  # for cwv
    tmp_avg_lse = tmp + '.avg_lse'
    tmp_delta_lse = tmp + '.delta_lse'
    tmp_cwv = tmp + '.cwv'  # column water vapor map
    tmp_lst = "{prefix}.lst".format(prefix=tmp)  # lst

    # basic equation for mapcalc
    global equation, citation_lst
    equation = "{result} = {expression}"

    # user input
    mtl_file = options['mtl']

    if not options['prefix']:
        b10 = options['b10']
        b11 = options['b11']
        t10 = options['t10']
        t11 = options['t11']

        if not options['clouds']:
            qab = options['qab']
            cloud_map = False

        else:
            qab = False
            cloud_map = options['clouds']

    elif options['prefix']:
        prefix = options['prefix']
        b10 = prefix + '10'
        b11 = prefix + '11'

        if not options['clouds']:
            qab = prefix + 'QA'
            cloud_map = False

        else:
            cloud_map = options['clouds']
            qab = False

    qapixel = options['qapixel']
    lst_output = options['lst']

    global cwv_output
    cwv_window_size = int(options['window'])
    cwv_output = options['cwv']

    # optional maps
    average_emissivity_map = options['average_emissivity']
    delta_emissivity_map = options['delta_emissivity']

    global landcover_map, emissivity_class
    landcover_map = options['landcover']
    emissivity_class = options['emissivity_class']

    # flags
    global info
    info = flags['i']
    keep_region = flags['k']
    colortable = flags['c']

    # ToDo:
    # timestamps = not(flags['t'])
    # shell = flags['g']

    #
    # Pre-production actions
    #

    # Set Region
    if not keep_region:
        grass.use_temp_region()  # safely modify the region
        msg = "\n|! Matching region extent to map {name}"

        # ToDo: check if extent-B10 == extent-B11? Unnecessary?
        # Improve below!

        if b10:
            run('g.region', rast=b10)
            msg = msg.format(name=b10)

        elif t10:
            run('g.region', rast=t10)
            msg = msg.format(name=t10)

        g.message(msg)

    elif keep_region:
        grass.warning(_('Operating on current region'))

    #
    # 1. Mask clouds
    #

    if cloud_map:
        # user-fed cloud map?
        msg = '\n|i Using {cmap} as a MASK'.format(cmap=cloud_map)
        g.message(msg)
        r.mask(raster=cloud_map, flags='i', overwrite=True)

    else:
        # using the quality assessment band and a "QA" pixel value
        mask_clouds(qab, qapixel)

    #
    # 2. TIRS > Brightness Temperatures
    #

    if mtl_file:

        # if MTL and b10 given, use it to compute at-satellite temperature t10
        if b10:
            # convert DNs to at-satellite temperatures
            t10 = tirs_to_at_satellite_temperature(b10, mtl_file)

        # likewise for b11 -> t11
        if b11:
            # convert DNs to at-satellite temperatures
            t11 = tirs_to_at_satellite_temperature(b11, mtl_file)

    #
    # Initialise a SplitWindowLST object
    #

    split_window_lst = SplitWindowLST(emissivity_class)
    citation_lst = split_window_lst.citation

    #
    # 3. Land Surface Emissivities
    #

    # use given fixed class?
    if emissivity_class:

        if split_window_lst.landcover_class is False:
            # replace with meaningful error
            g.warning('Unknown land cover class string')

        if emissivity_class == 'Random':
            msg = "\n|! Random emissivity class selected > " + \
                split_window_lst.landcover_class + ' '

        else:
            msg = '\n|! Retrieving average emissivities *only* for {eclass} '

        if info:
            msg += '| Average emissivities (channels 10, 11): '
            msg += str(split_window_lst.emissivity_t10) + ', ' + \
                str(split_window_lst.emissivity_t11)

        msg = msg.format(eclass=split_window_lst.landcover_class)
        g.message(msg)

    # use the FROM-GLC map
    elif landcover_map:

        if average_emissivity_map:
            tmp_avg_lse = average_emissivity_map

        if not average_emissivity_map:
            determine_average_emissivity(tmp_avg_lse, landcover_map,
                                         split_window_lst.average_lse_mapcalc)
        if delta_emissivity_map:
            tmp_delta_lse = delta_emissivity_map

        if not delta_emissivity_map:
            determine_delta_emissivity(tmp_delta_lse, landcover_map,
                                       split_window_lst.delta_lse_mapcalc)

    #
    # 4. Modified Split-Window Variance-Covariance Matrix > Column Water Vapor
    #

    if info and cwv_window_size != 3:
        msg = '\n|i Spatial window of size {n} for Column Water Vapor estimation: '
        msg = msg.format(n=cwv_window_size)
        g.message(msg)

    cwv = Column_Water_Vapor(cwv_window_size, t10, t11)
    citation_cwv = cwv.citation
    estimate_cwv_big_expression(tmp_cwv, t10, t11, cwv._big_cwv_expression())

    #
    # 5. Estimate Land Surface Temperature
    #

    if info and emissivity_class == 'Random':
        msg = '\n|* Will pick a random emissivity class!'
        grass.verbose(msg)

    estimate_lst(tmp_lst, t10, t11,
                 tmp_avg_lse, tmp_delta_lse, tmp_cwv,
                 split_window_lst.sw_lst_mapcalc)

    #
    # Post-production actions
    #

    # remove MASK
    r.mask(flags='r', verbose=True)

    # strings for metadata
    history_lst = 'Split-Window model: '
    history_lst += split_window_lst.sw_lst_mapcalc
    title_lst = 'Land Surface Temperature (C)'
    description_lst = ('Split-Window LST')
    units_lst = 'Celsius'
    source1_lst = citation_lst
    source2_lst = citation_cwv

    # history entry
    run("r.support", map=tmp_lst, title=title_lst,
        units=units_lst, description=description_lst,
        source1=source1_lst, source2=source2_lst,
        history=history_lst)

    # Celsius color table
    if colortable:
        g.message('\n|i Assigning the "celsius" color table to the LST map')
        run('r.colors', map=tmp_lst, color='celsius')

    # (re)name the LST product
    run("g.rename", rast=(tmp_lst, lst_output))

    # restore region
    if not keep_region:
        grass.del_temp_region()  # restoring previous region settings
        g.message("|! Original Region restored")

    # print citation
    if info:
        print '\nSource: ' + citation_lst


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    sys.exit(main())
