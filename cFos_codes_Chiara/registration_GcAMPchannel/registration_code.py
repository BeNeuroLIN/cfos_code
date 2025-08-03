from pathlib import Path
import os
import numpy as np
import nrrd
import datetime
import subprocess
import sys
import json


# These environmental variables need to be set
ants_bin_path = os.environ["ANTS_BIN_PATH"]  # even in windows, this must be unix format (ubuntu shell)
ants_use_threads = int(os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"])

def compute_volume_registration(source_stack_path, target_stack_path, registration_files_prefix):
    print(datetime.datetime.now(), "Running compute_volume_registration.", locals())

    if type(target_stack_path) is not list:
        target_stack_path = [target_stack_path]
    if type(source_stack_path) is not list:
        source_stack_path = [source_stack_path]

    source_stack_path_linux = [source_stack_path[i] for i in range(len(source_stack_path))]
    target_stack_path_linux = [target_stack_path[i] for i in range(len(target_stack_path))]
    registration_files_prefix_linux = registration_files_prefix

   
    registration_commands_list = [f"{ants_bin_path}/antsRegistration",
                                  "-v", "1", #version
                                  "-d", "3",#dimensionality
                                  "--float", "1",
                                  "--winsorize-image-intensities", "[0.005, 0.995]",
                                  "–-use-histogram-matching", "1",
                                  "-o", f"{registration_files_prefix_linux}_"]

    # Only do one for the initial moving transform, take always the first from the list
    registration_commands_list += ["--initial-moving-transform"]
    registration_commands_list += [f"[{target_stack_path_linux[0]},{source_stack_path_linux[0]},1]"]

    registration_commands_list += ["-t", "rigid[0.1]"] #the first linear transform
    for i in range(len(target_stack_path)):
        registration_commands_list += ["-m", f"MI[{target_stack_path_linux[i]},{source_stack_path_linux[i]},1,32,Regular,0.25]"]
    registration_commands_list += ["-c", "[3000x2000x2000x0,1e-8,50]",
                                   "-f", "12x8x4x2",
                                   "-s", "4x3x2x1"]

    registration_commands_list += ["-t", "Affine[0.1]"]
    for i in range(len(target_stack_path)):
        registration_commands_list += ["-m", f"MI[{target_stack_path_linux[i]},{source_stack_path_linux[i]},1,32,Regular,0.25]"]
    registration_commands_list += ["-c", "[4000x4000x4000x0,1e-8,100]",
                                   "-f", "12x8x4x2",
                                   "-s", "4x3x2x1vox"]

    registration_commands_list += ["-t", "SyN[0.05,6,0]"] 
    for i in range(len(target_stack_path)):
        registration_commands_list += ["-m", f"CC[{target_stack_path_linux[i]},{source_stack_path_linux[i]},1,2]"]
    registration_commands_list += ["-c", "[700x700x700x700x10,1e-7,50]",
                                  "-f", "12x8x4x2x1",
                                  "-s", "4x3x2x1x0"]  

    print(registration_commands_list)

    subprocess.run(registration_commands_list)


def apply_volume_registration_to_stack(registration_files_prefix_list, source_stack_path,
                                       target_stack_path, output_stack_path, use_inverted_transforms=False,
                                       interpolation_method="linear"):
    print(datetime.datetime.now(), "Running apply_volume_registration_to_stack.", locals())

    source_stack_path_linux = source_stack_path
    target_stack_path_linux = target_stack_path
    output_stack_path_linux = output_stack_path


    readdata, header = nrrd.read(source_stack_path)
    pad_out = np.percentile(np.r_[readdata[:5].flatten(), readdata[-5:].flatten(), readdata[:, :5].flatten(), readdata[:, -5:].flatten()], 5)
    registration_commands_list = [f"{ants_bin_path}/antsApplyTransforms",
                                  "--float",   
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

    registration_commands_list += ["-o", f"{output_stack_path_linux}"]     
    subprocess.run(registration_commands_list)


def printUsageAndExit():
    print("Usage:")
    print("zebrafish_registration.py <jsonfile> ")
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
        reference_brains_path=Path(setting['reference_image_path'])
        root_path = Path(setting['moving_image_path'])
        reference_file = setting['reference_image_file']
        moving_image_names=setting['moving_image_names']
        for group_name in moving_image_names:
            compute_volume_registration(source_stack_path=root_path / f"{group_name}.nrrd", target_stack_path=reference_brains_path / f"{reference_file}.nrrd", 
                                        registration_files_prefix=root_path / f"{group_name}_to_zebraRef_reference") #output file location/name
            apply_volume_registration_to_stack(registration_files_prefix_list=[root_path / f"{group_name}_to_zebraRef_reference"],
                                           source_stack_path=root_path / f"{group_name}.nrrd",
                                           target_stack_path=reference_brains_path / f"{reference_file}.nrrd",
                                           output_stack_path=root_path / f"{group_name}_registered.nrrd")
