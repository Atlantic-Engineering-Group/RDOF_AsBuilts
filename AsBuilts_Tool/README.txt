RDOF As Built Tool - v1 Created by Chris Grant on 09/30/2021. 
    
    Tool extracts RDOF data from GISMO and exports an AsBuilt geodatabase and generates a splice sheet from 
	that data. Warning - This script is largely dependent on the design data in the RDOF database. If aspects 
    of the service are changed, such as field attributes or schema, it could effect the performance or prohibit 
    the functionality of the code. This code will likely need regular maintenance and versioning. 
    
    Contact: chris.grant@aeg.cc
    
    Requirements:
    Access to GISMO and ArcPro. Note, a blank project should be set up and used specifically for this tool. The tool
    clears the project GDB on every run, so do not store important data in the project GDB. 
I/O:
    Input: Takes in an RDOF OLT/LCP name and output folder location. 
    Output: As Built geodatabase and corresponding splice sheet. 