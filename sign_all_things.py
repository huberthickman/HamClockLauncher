import pathlib
import argparse
import subprocess
import os
from dotenv import load_dotenv
load_dotenv()

#
# This script will sign all the executables, libraries, etc. needed to prepare for submission to the Apple Notary service.
#

# There are some adhoc looking bits here, but I have found looping through and signing everything multiple times takes  care of
# signing dependency ordering issues - if you are including extra executables and libraries, these
# ordering problems do exist.
#
# the next pass signs the Python executable and the app launcher executable.
#
# The last thing signed is the .app directory itself
#

parser = argparse.ArgumentParser(description='Sign all the required files in the app directory')
parser.add_argument('--directory', action='store', type=str, required=True)
parser.add_argument('--arch', action='store', type=str, required=False, help='set to x86_64 to compile for Intel on arm')
args = parser.parse_args()

EXTENSIONS = {'.so','.dylib' }
signing_id = ''

# First sign the easy stuff
p = pathlib.Path(args.directory)
print(p)
things_to_sign = p.glob('**/*')

if args.arch is not None and args.arch == 'x86_64':
    arch_str = '/usr/bin/arch -x86_64 '
else:
    arch_str = ''

def sign_files(file_to_sign, arch_str):
    full_path_obj = file_to_sign.resolve()

    # Convert the Path object to a string for standard use
    full_path_str = str(full_path_obj)

    # Get the filename with its extension
    filename_with_ext = full_path_obj.name
    command= arch_str + 'codesign --force --options runtime --timestamp --entitlements entitlements.plist --verbose --sign ' + "'"+os.getenv('DEV_SIGNING_NAME')+"'" + ' ' + full_path_str
    print(command)
    ret = subprocess.run(command, shell=True, capture_output=True)
    print(ret)


#
# First pass, sign executables 3 times (don't laugh, it works)
#
for i in range(0,3):
    for path in things_to_sign:
        if path.suffix in EXTENSIONS:
            print('NEED TO SIGN due suffix ', path)
            sign_files(path, arch_str)
        elif (os.access(str(path), os.X_OK) and os.path.isfile(str(path))):
            print("NEED TO SIGN -- executable ",path)
            sign_files(path, arch_str)

things_to_sign = p.glob('**/*')

for i in range(0,2):
    for path in things_to_sign:
        if path.name == 'Python' or path.name == os.getenv('APP_EXECUTABLE'):
            sign_files(path, arch_str)

things_to_sign = p.glob('**/*')

print(".")
#sign the app too last
for path in things_to_sign:
    if path.name == os.getenv('APP_EXECUTABLE')+'.app':
        print("==== signing app dir at", str(path))
        sign_files(path, arch_str)


