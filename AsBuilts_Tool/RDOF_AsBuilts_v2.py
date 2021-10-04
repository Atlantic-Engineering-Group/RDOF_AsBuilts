import arcpy
import pandas as pd
import os
from os.path import join as join
from datetime import datetime
from collections import Counter

date = datetime.now()
aprx = arcpy.mp.ArcGISProject("CURRENT")
maps = aprx.listMaps("Map")[0]
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = True
scratch = arcpy.env.workspace
# cab_list = arcpy.GetParameterAsText(0)
lcp = arcpy.GetParameterAsText(0)
lcpNameFixed = lcp.replace('-', '_')
outpath = arcpy.GetParameter(1)
outGDB = arcpy.CreateFileGDB_management(outpath, f"RDOF_AsBuilts_{lcp}_{date.strftime('%Y%m%d')}.gdb")
arcpy.AddMessage(outpath)
''' 
    RDOF As Built- Created by Chris Grant on 09/29/2021. 

    Tool extracts RDOF data from GISMO and creates As Built .gdb and corresponding splice sheet. Warning - 
    This script is largely dependent on the design data in the RDOF database. If aspects of the service are changed, 
    such as field attributes or schema, it could effect the performance or prohibit the functionality of the code. 

    Contact: chris.grant@aeg.cc

    Requirements:
    Access to GISMO and ArcPro. Note, a blank project should be set up and used specifically for this tool. The tool
    clears the project GDB on every run, so do not store important data in the project GDB. 
I/O:
    Input: Takes in an RDOF OLT/LCP name and output folder location. 
    Output: Exports As Built geodatabase and splice sheet.  

'''


def clear_gdb():
    arcpy.AddMessage('Clearing Geodatabase...')

    fcList = []
    walk = arcpy.da.Walk(scratch, datatype="FeatureClass")
    for dirpath, dirnames, filenames in walk:
        for filename in filenames:
            fcList.append(os.path.join(dirpath, filename))
    for item in fcList:
        arcpy.management.Delete(item)
    fcTables = arcpy.ListTables()
    print(fcTables)
    for table in fcTables:
        arcpy.management.Delete(f"{scratch}\\{table}")


def import_layers():
    arcpy.AddMessage('Importing layers from GISMO...')

    rdof_design = 'https://gismo.aeg.cc/server/rest/services/RDOF_Design/RDOF_Design/FeatureServer'

    rdof_list = ['Structure', 'Slack Loop', 'Fiber Equipment', 'Proposed Cabinets', 'Merit Huts',
                 'Proposed Down Guy', 'Riser', 'Pole', 'Splice Closure', 'Conduit', 'FiberCable',
                 'DropFiber', 'High Level Fiber Design', 'Overbuild High Level Design', 'Merit Routes',
                 'CBGs', 'Proposed OLT/LCP Boundaries', 'Hut Boundaries', 'Overbuild Areas',
                 'Upper Peninsula ROW', 'Railroads', 'Address', 'Parcels', 'Waterway', 'Served Address',
                 'Merit Splices', 'Permit Polygons', 'Do Not Build', 'Cloverland Poles', 'Cloverland Service Point']

    names = ['FiberCable', "Proposed OLT/LCP Boundaries", "DropFiber", "Splice Closure", "Served Address",
             "Fiber Equipment", 'Conduit', 'Structure']

    designs = {v: f'{rdof_design}/{i}' for i, v in enumerate(rdof_list)}

    for item in rdof_list:
        if item in names:
            maps.addDataFromPath(designs[item])

    layers_dict = {}
    for layer in maps.listLayers():
        if layer.name in names:
            cleaned_name = layer.name.replace(' ', '_').replace('/', '')
            layers_dict[cleaned_name] = layer

    results_dict = {}

    for name, layer in layers_dict.items():
        arcpy.conversion.FeatureClassToFeatureClass(layer, scratch, f"{name}_copy")
        results_dict[name] = arcpy.management.MakeFeatureLayer(f"{scratch}\\{name}_copy", f"{name}_copy").getOutput(0)
        maps.addLayer(results_dict[name], 'TOP')
        maps.removeLayer(layer)

############# Start QC calcs and exports #############
def export_asBuilt(lcp):
    '''
    Exports as built .gdb from RDOF. Warning - if schema specifications for 'As Built' change then this script will
    have to be updated and versioned.
    :param lcp: Raw lcp name used for query expressions.
    :param lcpNameFixed: lcpNameFixed: LCP name that removes any illegal chars (- particularly) done in main()
    :return: None
    '''
    arcpy.AddMessage('Collecting LCP features...')
    global totalConduit, totalFiber, lcpSplices, lcpEquipment, lcpStructures, servedAdds, dropFiber
    arcpy.env.workspace = scratch
    arcpy.env.overwriteOutput = True

    # Query out LCP boundary
    arcpy.FeatureClassToFeatureClass_conversion('Proposed_OLTLCP_Boundaries_copy', scratch, f'{lcpNameFixed}_Boundary',
                                                f"cab_id = '{lcp}'")

    # Served Addresses
    arcpy.SpatialJoin_analysis('Served_Address_copy', f'{lcpNameFixed}_Boundary', f'{lcpNameFixed}_Total_Adds',
                               'JOIN_ONE_TO_ONE', 'KEEP_COMMON', '', 'WITHIN')
    arcpy.FeatureClassToFeatureClass_conversion(f'{lcpNameFixed}_Total_Adds', outGDB, "Served_Address",
                                                             "inventorystatus = 'RI'")
    servedAdds = arcpy.management.MakeFeatureLayer(f"{outGDB}\\Served_Address", f"Served_Address").getOutput(0)
    maps.addLayer(servedAdds, 'TOP')

    # Drop Fiber
    dropFiber = arcpy.SpatialJoin_analysis('DropFiber_copy', f'{lcpNameFixed}_Boundary', f'{lcpNameFixed}_Total_Drops',
                                           'JOIN_ONE_TO_ONE', 'KEEP_COMMON', None, 'WITHIN')
    arcpy.FeatureClassToFeatureClass_conversion(dropFiber, outGDB, "dropFiber", "inventory_status_code IN ('RI', 'AB')")

    # Conduit
    arcpy.Intersect_analysis(["Conduit_copy", f'{lcpNameFixed}_Boundary'], f'{lcpNameFixed}_Total_Conduit', '', '', 'LINE')
    arcpy.FeatureClassToFeatureClass_conversion(f'{lcpNameFixed}_Total_Conduit', outGDB, "Conduit", "inventory_status_code = 'AB'")

    # Fiber
    fiber = arcpy.Intersect_analysis(["FiberCable_copy", f'{lcpNameFixed}_Boundary'], f'{lcpNameFixed}_Total_Fiber', '', '', 'LINE')
    arcpy.FeatureClassToFeatureClass_conversion(fiber, outGDB, "FiberCable", "inventory_status_code = 'AB'")

    # Splices
    lcpSplices = arcpy.SpatialJoin_analysis("Splice_Closure_copy", f'{lcpNameFixed}_Boundary',
                                            f'{lcpNameFixed}_Total_SpliceClosures', 'JOIN_ONE_TO_ONE', 'KEEP_COMMON', '',
                                            'WITHIN')
    arcpy.FeatureClassToFeatureClass_conversion(lcpSplices, outGDB, "SpliceClosure", "inventory_status_code IN ('AB', 'PS')")

    # Fiber Equipment
    lcpEquipment = arcpy.SpatialJoin_analysis('Fiber_Equipment_copy', f'{lcpNameFixed}_Boundary',
                                              f'{lcpNameFixed}_Total_FiberEquipment', 'JOIN_ONE_TO_ONE', 'KEEP_COMMON',
                                              '', 'WITHIN')
    arcpy.FeatureClassToFeatureClass_conversion(lcpEquipment, outGDB, "Fiber_Equipment", "inventory_status_code = 'AB'")

    #Structures
    lcpStructures = arcpy.SpatialJoin_analysis('Structure_copy', f'{lcpNameFixed}_Boundary',
                                              f'{lcpNameFixed}_Total_Structures', 'JOIN_ONE_TO_ONE', 'KEEP_COMMON',
                                              '', 'WITHIN')
    arcpy.FeatureClassToFeatureClass_conversion(lcpStructures, outGDB, "Structure", "inventorystatuscode = 'AB'")


def splice_sheet(lcp):

    arcpy.env.workspace = scratch
    arcpy.env.overwriteOutput = True
    '''Perform Joins'''

    arcpy.SpatialJoin_analysis('DropFiber_copy', 'Served_Address', f'{lcpNameFixed}_Adds_Drop', 'JOIN_ONE_TO_ONE',
                               'KEEP_COMMON', '', 'INTERSECT')
    # arcpy.SpatialJoin_analysis(f'{lcpNameFixed}_Total_Drops', 'Served_Address', f'{lcpNameFixed}_Adds_Drop', 'JOIN_ONE_TO_ONE',
    #                            'KEEP_COMMON', '', 'INTERSECT')
    arcpy.DeleteField_management(f'{lcpNameFixed}_Adds_Drop', 'cable_name')

    arcpy.SpatialJoin_analysis(f'{lcpNameFixed}_Adds_Drop', 'FiberCable_copy', f'{lcpNameFixed}_Adds_Drop_Fiber',
                               'JOIN_ONE_TO_ONE', 'KEEP_COMMON', None, 'INTERSECT')

    arcpy.management.AddField('Splice_Closure_copy', 'NAP', "TEXT")
    arcpy.CalculateField_management('Splice_Closure_copy', "NAP", "!spliceenclosuretype![0] + str(!OBJECTID!)",
                                    'PYTHON', None, 'TEXT')

    arcpy.SpatialJoin_analysis(f'{lcpNameFixed}_Adds_Drop_Fiber', 'Splice_Closure_copy',
                               f'{lcpNameFixed}_Adds_Drop_Fiber_Splice', 'JOIN_ONE_TO_ONE', 'KEEP_COMMON', '',
                               'INTERSECT')

    arcpy.SpatialJoin_analysis(f'{lcpNameFixed}_Adds_Drop_Fiber_Splice', 'ESC_C02_Total_Structures',
                               f'{lcpNameFixed}_Adds_Drop_Fiber_Splice_Structure', 'JOIN_ONE_TO_ONE', 'KEEP_COMMON', '',
                               'INTERSECT')

    arcpy.CalculateField_management(lcpEquipment, "structure_name", "!structure_name!.replace('_', '')", 'PYTHON', None, 'TEXT')
    arcpy.TableToExcel_conversion(lcpEquipment, f'{outpath}\\{lcpNameFixed}_FiberEquipment.xlsx', 'ALIAS')

    arcpy.management.AddField(f'{lcpNameFixed}_Adds_Drop_Fiber_Splice_Structure', 'Assigned_Ports', "TEXT")
    arcpy.CalculateField_management(f'{lcpNameFixed}_Adds_Drop_Fiber_Splice', "Assigned_Ports",
                                    "!assignedfiber!.split('-')[0]", 'PYTHON', None, 'TEXT')

    arcpy.management.AddField(f'{lcpNameFixed}_Adds_Drop_Fiber_Splice_Structure', 'OLT_PONfiber', "TEXT")
    arcpy.management.AlterField(f'{lcpNameFixed}_Adds_Drop_Fiber_Splice_Structure', 'structure_name_1', 'new_structure',
                                'new_structure')

    arcpy.TableToExcel_conversion(f'{lcpNameFixed}_Adds_Drop_Fiber_Splice_Structure',
                                  f'{outpath}\\{lcpNameFixed}AsBuilt_SpliceSheet.xlsx', 'ALIAS')

    for layer in maps.listLayers():
        maps.removeLayer(layer)

    arcpy.AddMessage('Formatting Dataset...')

    import pandas as pd
    pd.set_option('display.float_format', lambda x: '%.0f' % x)

    df = pd.read_excel(f'{outpath}\\{lcpNameFixed}AsBuilt_SpliceSheet.xlsx')
    df = df.fillna('null')
    df = df.astype(str)
    df.drop(df[df['Verification Status'] != 'RB'].index, inplace=True)

    # previous method - scanned fiber rows and extracted splitter.
    # df['Assigned Splitter'] = df.apply(','.join, axis=1).str.extract(r'(\w*SPL\w*)',
    #                                                                  expand=False).fillna('').str.replace(r'.SP$', '')

    # New method - should be more dependable. However is still dependent on designers input
    # df['Assigned Splitter'] = lcp.replace('-', '') + 'SPL' + df['Assigned Fiber Name'].str.strip('.0').apply(
    #     lambda x: '{0:0>2}'.format(x))
    df['Assigned Splitter'] = lcp.replace('-C0', '') + 'SP' + df['Assigned Fiber Name'].apply(lambda x: '{0:0>2}'.format(x))

    data = df[
        ['Address', 'City', 'Zip', 'NAP', 'Cable Name', 'Assigned Splitter', 'FiberCount', 'Row 7', 'Assigned_Ports',
         'Assigned Fiber Count', 'new_structure', 'OLT_PONfiber']].copy()

    data.columns = ['Address', 'City', 'Zip', 'NAP', 'Fiber Cable', 'Assigned Splitter', 'Assigned Port', 'Row 7',
                    'Assigned_Ports', 'AssignedFiberCount', 'Structure Name', 'OLT PON fiber']

    data.dropna(subset=['Address'], inplace=True)
    data.drop_duplicates(subset=['Address'], inplace=True)
    data['Fiber Cable'] = data['Fiber Cable'].str.replace('-C0', '')
    data['Structure Name'] = data['Structure Name'].str.replace('C0', '')

    # PON Fiber Assignment
    # data['OLT shelf at cabinet'] = ''
    data.loc[data['OLT PON fiber'] == data['OLT PON fiber'].fillna(0, inplace=True)]
    pon = df[df['Row 1'].str.contains('PON|F1')]
    pon['Row 1'].str.split(' ').str[1].str.strip(',')
    ponlabel = pon['Row 1'].values[0].split(' ')[1].strip(',')
    data.loc[:, 'OLT PON fiber'] = ponlabel.replace('C0', '')

    ''' Formatting Fiber Equipment to be joined into Splice Sheet'''

    fe = pd.read_excel(f'{outpath}\\{lcpNameFixed}_FiberEquipment.xlsx')

    fe.columns = ['OBJECTID', 'join_count', 'targetID', 'Splitter_Name', 'Inventory Status Code', 'Height',
                  'created_user', 'created_date', 'last_edited_user', 'edit_date', 'Equipment Type', 'F1', 'F2', 'CabID',
                  'F_Quantity', 'Type_ID', 'shape_len', 'Name', 'cu', 'cd', 'leu', 'led', 'hhpcount', 'isc', 'c', 'pp',
                  'pz', 'ls']

    fe_split = pd.DataFrame(fe.Splitter_Name.str.split('SPL', 1).tolist(), columns=['splitter', 'number'])
    fe_split['Count'] = fe.F1
    fe_split['number'] = fe_split['number'].apply(lambda x: '{0:0>2}'.format(x))

    fe_split['Assigned Splitter'] = fe_split['splitter'].str.replace('C0', '') + 'SP' + fe_split['number']

    merge = data.merge(fe_split, left_on='Assigned Splitter', right_on='Assigned Splitter', how="outer")

    # merge['Count'] == merge['Assigned Splitter'].str.split('P').str[1]

    '''Sets shelf levels'''

    # merge.loc[merge['Count'].astype(int) <= 16, 'OLT shelf at cabinet'] = '1st'
    # merge.loc[merge['Count'].astype(int) > 16, 'OLT shelf at cabinet'] = '2nd'
    # merge.loc[merge['Count'].astype(int) > 32, 'OLT shelf at cabinet'] = '3rd'
    # merge.loc[merge['Count'].astype(int) > 49, 'OLT shelf at cabinet'] = '4th'

    final = merge[['Address', 'City', 'Zip', 'NAP', 'Fiber Cable', 'Assigned Splitter', 'Assigned Port',
                   'AssignedFiberCount', 'OLT PON fiber', 'Structure Name', 'Count']].copy()

    final = final.dropna().copy()

    final.sort_values(['NAP', 'Assigned Port', 'Assigned Splitter'], ascending=[True, True, True], inplace=True)
    final.to_excel(f'{outpath}\\{lcpNameFixed}AsBuilt_SpliceSheet.xlsx', index=False)
    arcpy.AddMessage('Script complete. Check output location.')


clear_gdb()
import_layers()
export_asBuilt(lcp)
splice_sheet(lcp)

