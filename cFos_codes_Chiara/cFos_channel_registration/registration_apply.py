from pathlib import Path
import os
import numpy as np
import nrrd
import xml.etree.ElementTree as ET
import datetime
import subprocess
import sys
import json



# These environmental variables need to be set
ants_bin_path = os.environ["ANTS_BIN_PATH"]  # even in windows, this must be unix format (ubuntu shell)
ants_use_threads = int(os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"])


def apply_volume_registration_to_stack(registration_files_prefix_list, source_stack_path,
                                       target_stack_path, output_stack_path, use_inverted_transforms=False,
                                       interpolation_method="linear"):
    print(datetime.datetime.now(), "Running apply_volume_registration_to_stack.", locals())

    source_stack_path_linux = source_stack_path
    target_stack_path_linux = target_stack_path
    output_stack_path_linux = output_stack_path


    # get the brightness of the border frame of the source image
    readdata, header = nrrd.read(source_stack_path)
    pad_out = np.percentile(np.r_[readdata[:5].flatten(), readdata[-5:].flatten(), readdata[:, :5].flatten(), readdata[:, -5:].flatten()], 5)
    print("pad_out :" +str(pad_out))
    print(pad_out)
    #pad_out=50.0
    registration_commands_list = [f"{ants_bin_path}/antsApplyTransforms",
                                  "--float",    # use single precision (as for the registration)
                                  "-v", "1",
                                  "-d", "3",
                                  "-f", f"{pad_out}",#padding for border areas
                                  "-i", f"{source_stack_path_linux}",
                                  "-r", f"{target_stack_path_linux}",
                                  "-n", f"{interpolation_method}"]

    if use_inverted_transforms is False:
        for registration_files_prefix in registration_files_prefix_list:
            registration_files_prefix_linux = registration_files_prefix

            registration_commands_list += ["--transform", f"{registration_files_prefix_linux}_1Warp.nii.gz",
                                           "--transform", f"{registration_files_prefix_linux}_0GenericAffine.mat"]
    else:
        for registration_files_prefix in registration_files_prefix_list[::-1]:
            registration_files_prefix_linux = registration_files_prefix

            registration_commands_list += ["--transform", f"[{registration_files_prefix_linux}_0GenericAffine.mat, 1]",
                                           "--transform", f"{registration_files_prefix_linux}_1InverseWarp.nii.gz"]

    registration_commands_list += ["-o", f"{output_stack_path_linux}"]     ## nii.gz???

    subprocess.run(registration_commands_list)

    # ANTS makes it a 32bit float tiff, convert it back to 16bit uint
    #readdata, header = nrrd.read(str(output_stack_path))
    #readdata = readdata.astype(np.uint16)
    #header["encoding"] = 'gzip'
    #header["type"] = 'uint16'
    #nrrd.write(str(output_stack_path), readdata, header)

def printUsageAndExit():
    print("Usage:")
    print("register_afs_zbrain.py <jsonfile> ")
    print("")
    sys.exit()


if __name__ == '__main__':

    # These enivornmental variables need to be set
   
    if(len(sys.argv) not in [2]):
        printUsageAndExit()
    settings_json = sys.argv[1]
    f=open(settings_json, 'r')
    settings = json.load(f)
    print(settings)
    for setting in settings:
        reference_brains_path=Path(setting['reference_path'])
        root_path = Path(setting['root_path'])
        reference_file = setting['reference_file']
        group_names=setting['group_names']
        for group_name in group_names:
            file_name=group_name.replace("C2", "C1")
            #file_name=group_name[2:]
            #file_name=group_name[:-4]
            #print(file_name)
            #file_name=file_name+"_green"
            #file_name="C3"+file_name
            #print(file_name)
            apply_volume_registration_to_stack(registration_files_prefix_list=[reference_brains_path / f"{file_name}_to_zebraRef_reference"],
                                           source_stack_path=root_path / f"{group_name}.nrrd",
                                           target_stack_path=reference_brains_path / f"{reference_file}.nrrd",
                                           output_stack_path=root_path / f"{group_name}_registered1.nrrd")
    # this comes from the command line
    #filepath = Path(sys.argv[1]).resolve()
