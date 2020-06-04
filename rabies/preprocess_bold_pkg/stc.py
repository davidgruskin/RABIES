from nipype.pipeline import engine as pe
from nipype.interfaces.utility import Function
from nipype.interfaces import utility as niu

def init_bold_stc_wf(tr, tpattern, name='bold_stc_wf'):
    """
    This workflow performs :abbr:`STC (slice-timing correction)` over the input
    :abbr:`BOLD (blood-oxygen-level dependent)` image.

    **Parameters**

        name : str
            Name of workflow (default: ``bold_stc_wf``)

    **Inputs**

        bold_file
            BOLD series NIfTI file
        skip_vols
            Number of non-steady-state volumes detected at beginning of ``bold_file``

    **Outputs**

        stc_file
            Slice-timing corrected BOLD series NIfTI file

    """
    workflow = pe.Workflow(name=name)
    inputnode = pe.Node(niu.IdentityInterface(fields=['bold_file', 'skip_vols']), name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(fields=['stc_file']), name='outputnode')

    slice_timing_correction = pe.Node(Function(input_names=['in_file', 'ignore', 'tr', 'tpattern'],
                              output_names=['out_file'],
                              function=apply_STC),
                     name='slice_timing_correction')

    workflow.connect([
        (inputnode, slice_timing_correction, [('bold_file', 'in_file'),
                                              ('skip_vols', 'ignore')]),
        (slice_timing_correction, outputnode, [('out_file', 'stc_file')]),
    ])

    return workflow

def apply_STC(in_file, ignore=0, tr='1.0s', tpattern='alt-z'):
    '''
    This functions applies slice-timing correction on the anterior-posterior
    slice acquisition direction. The input image, assumed to be in RAS orientation
    (accoring to nibabel; note that the nibabel reading of RAS corresponds to
     LPI for AFNI). The A and S dimensions will be swapped to apply AFNI's
    3dTshift STC with a quintic fitting function, which can only be applied to
    the Z dimension of the data matrix. The corrected image is then re-created with
    proper axes and the corrected timeseries.
    '''

    import os
    import SimpleITK as sitk
    import numpy as np

    img = sitk.ReadImage(in_file, int(os.environ["rabies_data_type"]))

    #get image data
    img_array=sitk.GetArrayFromImage(img)[ignore:,:,:,:]

    shape=img_array.shape
    new_array=np.zeros([shape[0],shape[2],shape[1],shape[3]])
    for i in range(shape[2]):
        new_array[:,i,:,:]=img_array[:,:,i,:]

    image_out = sitk.GetImageFromArray(new_array, isVector=False)
    sitk.WriteImage(image_out, 'STC_temp.nii.gz')

    command='3dTshift -quintic -prefix temp_tshift.nii.gz -tpattern %s -TR %s STC_temp.nii.gz' % (tpattern,tr,)
    if os.system(command) != 0:
        raise ValueError('Error in '+command)

    tshift_img = sitk.ReadImage('temp_tshift.nii.gz', int(os.environ["rabies_data_type"]))
    tshift_array=sitk.GetArrayFromImage(tshift_img)

    new_array=np.zeros(shape)
    for i in range(shape[2]):
        new_array[:,:,i,:]=tshift_array[:,i,:,:]
    image_out = sitk.GetImageFromArray(new_array, isVector=False)

    from rabies.preprocess_bold_pkg.utils import copyInfo_4DImage
    image_out=copyInfo_4DImage(image_out, img, img)

    out_file=os.path.abspath(os.path.basename(in_file).split('.nii.gz')[0]+'_tshift.nii.gz')
    print(out_file)
    sitk.WriteImage(image_out, out_file)
    return out_file
