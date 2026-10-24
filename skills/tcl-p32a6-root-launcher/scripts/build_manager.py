"""Build upstream phh Superuser with installed Android tools, without Gradle."""
from pathlib import Path
import os, secrets, subprocess, zipfile, xml.etree.ElementTree as ET
import argparse

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True,help='Pinned phhusson/Superuser checkout')
p.add_argument('--sdk',type=Path,required=True)
p.add_argument('--java-home',type=Path,required=True)
p.add_argument('--build-tools',default='35.0.1')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
BASE=a.output.resolve()
if BASE.exists():
    raise SystemExit('Use a new output directory; retain existing signing keys for subsequent updates')
BASE.mkdir(parents=True,mode=0o700)
APP = a.source.resolve() / 'Superuser'
WIDGET = a.source.resolve() / 'Widgets/Widgets'
BUILD = BASE / 'manager-build'
SDK = a.sdk.resolve()
TOOLS = SDK / 'build-tools' / a.build_tools
JAVA = a.java_home.resolve()
ANDROID = SDK / 'platforms/android-25/android.jar'
ENV = dict(os.environ, JAVA_HOME=str(JAVA))
for name in ['gen','classes','dex']:
    (BUILD/name).mkdir(parents=True, exist_ok=True)

def run(args):
    subprocess.run([str(x) for x in args], check=True, env=ENV)

NS = 'http://schemas.android.com/apk/res/android'
ET.register_namespace('android', NS)
tree = ET.parse(APP/'AndroidManifest.xml')
root = tree.getroot()
for element in root.iter():
    value = element.get('{'+NS+'}name')
    if value and value.startswith('.'):
        element.set('{'+NS+'}name', 'com.koushikdutta.superuser'+value)
sdk = ET.Element('uses-sdk', {'{'+NS+'}minSdkVersion':'14', '{'+NS+'}targetSdkVersion':'22'})
root.insert(0, sdk)
tree.write(BUILD/'AndroidManifest.xml', encoding='utf-8', xml_declaration=True)
run([TOOLS/'aapt','package','-f','-m','--auto-add-overlay',
     '--extra-packages','com.koushikdutta.widgets','--rename-manifest-package','me.phh.superuser',
     '-M',BUILD/'AndroidManifest.xml','-S',APP/'res','-S',WIDGET/'res',
     '-A',APP/'assets','-I',ANDROID,'-J',BUILD/'gen','-F',BUILD/'resources.apk'])
sources = list((APP/'src').rglob('*.java')) + list((WIDGET/'src').rglob('*.java')) + list((BUILD/'gen').rglob('*.java'))
jars = list((WIDGET/'libs').glob('*.jar'))
run([JAVA/'bin/javac','-source','8','-target','8','-encoding','UTF-8',
     '-classpath',os.pathsep.join(map(str,[ANDROID]+jars)),
     '-d',BUILD/'classes',*sources])
run([JAVA/'bin/jar','cf',BUILD/'classes.jar','-C',BUILD/'classes','.'])
run([TOOLS/'d8','--min-api','14','--lib',ANDROID,'--output',BUILD/'dex',BUILD/'classes.jar',*jars])
with zipfile.ZipFile(BUILD/'resources.apk') as zin, zipfile.ZipFile(BUILD/'unsigned.apk','w') as zout:
    for item in zin.infolist():
        zout.writestr(item,zin.read(item.filename))
    for dex in (BUILD/'dex').glob('*.dex'):
        zout.write(dex,dex.name)
run([TOOLS/'zipalign','-f','4',BUILD/'unsigned.apk',BUILD/'aligned.apk'])
password = BASE/'signing-password.txt'
keystore = BASE/'tv-superuser.jks'
if not keystore.exists():
    password.write_text(secrets.token_urlsafe(32))
    password.chmod(0o600)
    run([JAVA/'bin/keytool','-genkeypair','-keystore',keystore,'-storepass:file',password,
         '-keypass:file',password,'-alias','tv-superuser','-keyalg','RSA','-keysize','3072',
         '-validity','3650','-dname','CN=Local TCL TV Superuser Build'])
    keystore.chmod(0o600)
run([TOOLS/'apksigner','sign','--ks',keystore,'--ks-key-alias','tv-superuser',
     '--ks-pass','file:'+str(password),
     '--out',BASE/'Superuser-local.apk',BUILD/'aligned.apk'])
run([TOOLS/'apksigner','verify','--verbose',BASE/'Superuser-local.apk'])
