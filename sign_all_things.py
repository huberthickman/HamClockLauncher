import pathlib
import argparse
import subprocess
import os
from dotenv import load_dotenv
load_dotenv()

#
# This script will sign all the executables, libraries, etc. needed to prepare for submission to the Apple Notary service.
#

# There are some adhoc looking bits here, but I have found looping through and signing everything multiple times takes are care of
# signing dependency ordering issues.
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
    arch_str = 'arch -x86_64 '
else:
    arch_str = ''


#
# First pass, sign executables 3 times (don't laugh, it works)
#
for i in range(0,3):
    for path in things_to_sign:
        #print(path)
        if path.suffix in EXTENSIONS:
            print('NEED TO SIGN due suffix ', path)
            ret = subprocess.run([arch+str +'codesign', '--force' ,'--options', 'runtime','--timestamp', '--entitlements', 'entitlements.plist', '--verbose', '--sign', os.getenv('DEV_SIGNING_NAME'), str(path)], capture_output=True)
            print(ret)
        elif (os.access(str(path), os.X_OK) and os.path.isfile(str(path))):
            print("NEED TO SIGN -- executable ",path)
            ret = subprocess.run(
                [arch+str +'codesign', '--force', '--options', 'runtime', '--timestamp', '--entitlements', 'entitlements.plist','--verbose', '--sign', os.getenv('DEV_SIGNING_NAME'),
                 str(path)], capture_output=True)
            print(ret)

things_to_sign = p.glob('**/*')

for i in range(0,2):
    for path in things_to_sign:
        #print(path)
        if path.name == 'Python' or path.name == os.getenv('APP_EXECUTABLE'):
            ret = subprocess.run(
                [arch+str +'codesign', '--force', '--options', 'runtime', '--timestamp', '--entitlements', 'entitlements.plist',
                 '--verbose', '--sign', os.getenv('DEV_SIGNING_NAME'), str(path)], capture_output=True)
            print(ret)

things_to_sign = p.glob('**/*')

print(".")
#sign the app too last
for path in things_to_sign:
    print(path)
    if path.name == os.getenv('APP_EXECUTABLE')+'.app':
        print("==== signing app dir at", str(path))
        ret = subprocess.run(
                    [arch+str +'codesign', '--force', '--options', 'runtime', '--timestamp', '--entitlements', 'entitlements.plist',
                     '--verbose', '--sign', os.getenv('DEV_SIGNING_NAME'), str(path)], capture_output=True)
        print(ret)

