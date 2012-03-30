import glob
import os
import shutil
import re
import tempfile
from warnings import warn
from write_report import report
import sqlite3

try:
    import pyxnat
except:
    pass

from nipype.interfaces.base import (TraitedSpec, traits, File, Directory,
                                    BaseInterface, InputMultiPath, isdefined,
                                    OutputMultiPath, DynamicTraitedSpec,
                                    Undefined, BaseInterfaceInputSpec)
from nipype.utils.filemanip import (copyfile, list_to_filename,
                                    filename_to_list)
from nipype.interfaces.io import IOBase
import logging
iflogger = logging.getLogger('interface')


class ReportSinkInputSpec(DynamicTraitedSpec, BaseInterfaceInputSpec):
    base_directory = Directory(
        desc='Path to the base directory for writing report.')
    
    container = traits.Str(desc = 'Folder within base directory in which to store output')
    _outputs = traits.Dict(traits.Str, value={}, usedefault=True)
    _outputs_order = []
    remove_dest_dir = traits.Bool(False, usedefault=True,
                                  desc='remove dest directory when copying dirs')

    def __setattr__(self, key, value):
        if key not in self.copyable_trait_names():
            if not isdefined(value):
                super(ReportSinkInputSpec, self).__setattr__(key, value)
            self._outputs[key] = value
            self._outputs_order.append(key)
        else:
            if key in self._outputs:
                self._outputs[key] = value
                self._outputs_order.append(key)
            super(ReportSinkInputSpec, self).__setattr__(key, value)


class ReportSink(IOBase):
    """ ReportSink module to write outputs to a pdf

This interface allows arbitrary creation of input attributes. The names of 
these attributes define the Report structure to create for display of images,
tables, and filenames.

This interface **cannot** be used in a MapNode as the inputs are
defined only when the connect statement is executed.

If an input ends with a .png or .jpg, the image will be displayed in the report
If an input is a list enclosed in more than 2 brackets, 
a table will be displayed:
        ex: [[ [['Month','Day'],[7,10],[12,25]] ]] --> 3x2 table with 
        'Month' and 'Day' as column headers, 7,10 in the first row
        and 12,25 in the second
Anything else is displayed as text

Examples
--------

>>> rs = ReportSink()
>>> rs.inputs.base_directory = 'results_dir'
>>> rs.inputs.subject = 'Subject 5'
>>> rs.inputs.table = [[ [['Month','Day'],[7,10],[12,25]] ]]
>>> rs.inputs.image = 'structural.png'
>>> rs.run() # doctest: +SKIP

"""
    input_spec = ReportSinkInputSpec

    def __init__(self, orderfields=None, infields=None, **kwargs):
        """
Parameters
----------
infields : list of str
Indicates the input fields to be dynamically created
"""

        super(ReportSink, self).__init__(**kwargs)
        undefined_traits = {}
        # used for mandatory inputs check
        self._infields = infields
        if infields:
            for key in infields:
                self.inputs.add_trait(key, traits.Any)
                self.inputs._outputs[key] = Undefined
                undefined_traits[key] = Undefined
        
        self._orderfields = orderfields
            
        self.inputs.trait_set(trait_change_notify=False, **undefined_traits)

    def _list_outputs(self):
        """Execute this module.
"""
        outdir = self.inputs.base_directory
        if not isdefined(outdir):
            outdir = '.'
        outdir = os.path.abspath(outdir)
        
        if isdefined(self.inputs.container):
            outdir = os.path.join(outdir, self.inputs.container)
            
        if not os.path.exists(outdir):
            try:
                os.makedirs(outdir)
            except OSError, inst:
                if 'File exists' in inst:
                    pass
                else:
                    raise(inst)
        
        # Begin Report
        rep = report(os.path.abspath(os.path.join(outdir,'Report.pdf')),'Report')
        
        # Loop through all inputs
        #for key, files in self.inputs._outputs.items():
        
        if self._orderfields:
            order = self._orderfields
        else:
            order = self.inputs._outputs_order
        
        for key in order:
            files = self.inputs._outputs[key]
            if not isdefined(files):
                continue
            iflogger.debug("key: %s files: %s"%(key, str(files)))
            files = filename_to_list(files)
            tempoutdir = outdir
            
            # Add name of input as a title
            rep.add_text('<b>%s</b>' % key.replace('_',' '))
            
            # flattening list
            if isinstance(files, list):
                if isinstance(files[0], list):
                    files = [item for sublist in files for item in sublist]
            
            for i, thing in enumerate(files):
                # Add a table, image or text
                if isinstance(thing,list):
                    rep.add_table(thing)
                else:
                    if thing.endswith('.png') or thing.endswith('.jpg'):
                        rep.add_text(os.path.split(thing)[1])
                        rep.add_image(thing)
                    else:
                        rep.add_text(thing)
        
        # write the report
        rep.write()
        return None
