#!/usr/bin/env python3
"""Execute actual TWinstall_zip -> mapped package -> ZIP/verifier/digest -> updater.

Native x86_64 builds of the current AOSP ZIP and TWRP sources run in a private
chroot with ordinary files and locally generated test keys. Actual BoringSSL
host archive and AOSP host libbase/log/libc++ are hashed dependencies. Property,
DataManager/progress and unmount are doubles. ABI-named updaters contain host
code solely to check selection; no ARM64/OTA payload/GUI/sideload/device run.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile
from nested_partition_path_test import method,ROOT,SRC

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=SRC/'twrpinstall/twinstall.cpp')
    ap.add_argument('--report',type=Path,default=ROOT/'logs/zip-install-chain.json')
    ap.add_argument('--arm64',action='store_true',help='Execute genuine target ELF through explicit QEMU exec boundary')
    ap.add_argument('--stock-os4',action='store_true',help='Original OS4 stable ZIP, delivered trust and A/B dispatch; harmless child only')
    ap.add_argument('--image',type=Path,help='Image for stock OS4 entry checks (default: current indexed image)')
    args=ap.parse_args();android=SRC.parents[1]
    if args.stock_os4 and args.arm64:ap.error('Select one execution scope')
    clang=android/'prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++'
    host=android/'out/host/linux-x86/lib64';base=android/'system/libbase';archive=android/'system/libziparchive'
    crypto=android/'out/soong/.intermediates/external/boringssl/libcrypto/linux_glibc_x86_64_static/libcrypto.a'
    text=args.source.read_text()
    signatures=['static int Prepare_Update_Binary(','static bool ParseUpdaterFraction(',
                'static bool ParseUpdaterSeconds(','static int Run_Update_Binary(',
                'bool isUpdatePkg(','int TWinstall_zip(']
    if 'static bool FindUpdaterBinary(' in text:signatures.insert(0,'static bool FindUpdaterBinary(')
    bodies=[method(text,s) for s in signatures]
    commands_text=(SRC/'twrpinstall/installcommand.cpp').read_text()
    bodies += [method(commands_text,'int\nupdate_binary_command('),method(commands_text,'bool verify_package_compatibility(')]
    if args.stock_os4:
        for sig in ['static int parse_build_number(', 'bool read_metadata_from_package(', 'void read_source_target_build(', 'static int check_newer_ab_build(', 'int\nabupdate_binary_command(']:
            bodies.append(method(re.sub(r'^\s*//[^\n]*','',commands_text,flags=re.M),sig))
    func=(SRC/'twrp_functions.cpp').read_text()
    bodies += [method(func,'int TWFunc::WaitForChild('),method(func,'static std::vector<std::string> SplitByCharset('),
               method(func,'std::vector<std::string> TWFunc::SplitString(const std::string& in, const char')]
    digest_text=(SRC/'digest/twrp_digest_driver.cpp').read_text()
    a=digest_text.index('namespace {');b=digest_text.index('} // namespace',a)+len('} // namespace')
    bodies += [digest_text[a:b],method(digest_text,'bool TwrpDigestDriver::CheckFileDigest('),
               method(digest_text,'bool TwrpDigestDriver::StreamFileToDigest(')]
    library=[archive/n for n in ['zip_archive.cc','zip_archive_stream_entry.cc','zip_cd_entry_map.cc','zip_error.cpp']]
    library += [SRC/n for n in ['twrpinstall/package.cpp','twrpinstall/verifier.cpp','twrpinstall/asn1_decoder.cpp',
                               'otautil/sysutil.cpp','otautil/rangeset.cpp','digest/twrp_digest.cpp']]
    names=['generic-stored','generic-deflated','signed-correct','signed-wrong-key','signed-tampered',
           'unsigned-required','no-keys','digest-md5-good','digest-sha256-good','digest-bad','digest-malformed',
           'digest-wrong-name','digest-missing','missing-file','truncated-zip','missing-updater','duplicate-name',
           'bad-compatibility','valid-compatibility','unmount-denied','updater-nonzero','updater-badprogress',
           'file-contexts','arch-first','arch-second','arch-none','arch-abi-property','generic-priority','extract-open-error',
           'arch-both','arch-reversed','arch-unsupported','arch-empty-fallback','arch-empty-all',
           'arch-no-properties','generic-no-properties']
    positive={'generic-stored','generic-deflated','signed-correct','digest-md5-good','digest-sha256-good','digest-missing',
              'valid-compatibility','file-contexts','arch-first','arch-second','arch-abi-property','generic-priority',
              'arch-both','arch-reversed','arch-empty-fallback','generic-no-properties'}
    cases=[];transcripts=[]
    target=None
    stock=None
    with tempfile.TemporaryDirectory(prefix='zip-install-chain-',dir=ROOT/'logs' if args.stock_os4 else None) as temp:
        work=Path(temp);harness=work/'test.cpp'
        if args.arm64:
            from zip_arm64_support import Arm64, BRIDGE
            target=Arm64(android,clang,work)
            names=['generic-stored','generic-deflated','signed-correct','signed-wrong-key','signed-tampered',
                   'digest-sha256-good','digest-bad','arch-first','arch-none','generic-priority','generic-no-properties',
                   'arch-unsupported','arch-empty-fallback','extract-open-error','updater-nonzero',
                   'updater-badprogress','target-link-failure','target-missing-lib','target-signal','target-partial-failure']
        if args.stock_os4:
            from zip_stock_support import Stock
            stock=Stock(work,args.image)
            names=stock.names
        inserted='\n'.join(bodies)
        if target:inserted=BRIDGE+inserted+'\n#undef execve\n#undef waitpid\n'
        fixture=(ROOT/'tests/zip_install_chain_test.cpp').read_text()
        if target:
            fixture=fixture.replace('static void SetProgress(float f,bool=false) {',
                'static void SetProgress(float f,bool=false) {printf("target_progress=%g\\n",f);')
            fixture=fixture.replace('static void ShowProgress(float f,int s) {',
                'static void ShowProgress(float f,int s) {printf("target_show_progress=%g,%d\\n",f,s);')
        if stock:fixture=stock.fixture(fixture)
        harness.write_text(fixture.replace('// PRODUCTION_METHODS',inserted))
        exe=work/'zip-install'
        cmd=[str(clang),'-std=c++23','-stdlib=libc++','-O1','-g','-Wno-deprecated-declarations',
             '-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DINCFS_SUPPORT_DISABLED=1','-DZLIB_CONST',
             '-I'+str(SRC/'twrpinstall/include'),'-I'+str(SRC/'otautil/include'),'-I'+str(SRC/'digest'),
             '-I'+str(base/'include'),'-I'+str(android/'external/boringssl/src/include'),
             '-I'+str(archive/'include'),'-I'+str(archive/'incfs_support/include'),
             '-I'+str(android/'system/logging/liblog/include'),'-I'+str(android/'system/core/libcutils/include'),
             '-I'+str(android/'external/googletest/googletest/include'),str(harness),*map(str,library),str(crypto),
             '-L'+str(host),'-Wl,-rpath,'+str(host),'-lbase','-llog','-lz','-ldl','-lpthread','-o',str(exe)]
        if stock:cmd.insert(1,'-DAB_OTA_UPDATER')
        subprocess.run(cmd,check=True)
        if stock:
            report=stock.run(exe,cmd,crypto,clang,[args.source,SRC/'twrpinstall/installcommand.cpp',SRC/'twrp_functions.cpp',SRC/'digest/twrp_digest_driver.cpp',ROOT/'tests/zip_install_chain_test.cpp',Path(__file__).resolve(),ROOT/'tests/nested_partition_path_test.py',*library,*list((SRC/'twrpinstall/include').rglob('*.h')),*list((SRC/'otautil/include').rglob('*.h'))])
            dest=args.report if args.report!=ROOT/'logs/zip-install-chain.json' else ROOT/'logs/zip-stock-os4.json'
            dest.write_text(json.dumps(report,indent=2)+'\n')
            return report['status']!='PASS'
        binaries={}
        for tag in ([] if target else ['generic','arm64','arm32']):
            p=work/('updater-'+tag)
            subprocess.run(['g++','-std=c++23','-O1','-static','-DUPDATER_TAG="'+tag+'"',str(ROOT/'tests/zip_install_fixture.cpp'),'-o',str(p)],check=True)
            binaries[tag]=p.read_bytes()
        if target:binaries=target.binaries
        dependencies={}
        ldd=subprocess.check_output(['ldd',str(exe)],text=True)
        for line in ldd.splitlines():
            m=re.search(r'(/[^\s()]+)',line)
            if m:
                p=Path(m[1]);dependencies[str(p)]=sha(p)
        for key in ['right','wrong']:
            for operands in [['genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(work/(key+'.key'))],
                             ['req','-new','-x509','-sha256','-key',str(work/(key+'.key')),'-out',str(work/(key+'.pem')),'-days','1','-subj','/CN=private-'+key]]:
                run=subprocess.run(['openssl',*operands],capture_output=True,text=True,check=True)
                transcripts.append(dict(operation=operands[0],exit=run.returncode))
        def key_zip(key):
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w') as z:z.writestr('private.x509.pem',(work/(key+'.pem')).read_bytes())
            return buf.getvalue()
        def sign(payload):
            signed=work/'signed-content';signed.write_bytes(payload[:-2]);sig=work/'signature.der'
            run=subprocess.run(['openssl','cms','-sign','-binary','-noattr','-md','sha256','-in',str(signed),
                  '-signer',str(work/'right.pem'),'-inkey',str(work/'right.key'),'-outform','DER','-out',str(sig)],
                  capture_output=True,text=True,check=True)
            der=sig.read_bytes();size=len(der)+6;assert size<65536
            return payload[:-2]+struct.pack('<H',size)+der+struct.pack('<H',size)+b'\xff\xff'+struct.pack('<H',size)
        generic='META-INF/com/google/android/update-binary'
        for name in names:
            jail=work/name;jail.mkdir()
            for dep in dependencies:
                dest=jail/Path(dep).relative_to('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(dep,dest);dest.chmod(0o755)
            shutil.copyfile(exe,jail/'test');(jail/'test').chmod(0o755)
            if target:target.stage(jail)
            for d in ['tmp','packages','system/etc/security']:(jail/d).mkdir(parents=True,exist_ok=True)
            (jail/'case-name').write_text(name)
            if name!='no-keys':(jail/'system/etc/security/otacerts.zip').write_bytes(key_zip('wrong' if name=='signed-wrong-key' else 'right'))
            buf=io.BytesIO();compression=zipfile.ZIP_DEFLATED if name=='generic-deflated' else zipfile.ZIP_STORED
            with zipfile.ZipFile(buf,'w',compression=compression) as z:
                if not name.startswith('arch-') and name!='missing-updater':
                    z.writestr(generic,binaries['undefined'] if name=='target-link-failure' else binaries['generic'])
                if name=='duplicate-name':z.writestr(generic,binaries['generic'])
                if name in ['arch-first','arch-abi-property','generic-priority','arch-both','arch-reversed',
                            'arch-empty-fallback','arch-empty-all','arch-no-properties']:
                    z.writestr(generic+'-arm64-v8a',binaries['arm64'])
                if name in ['arch-second','arch-reversed'] or (name=='arch-both' and not target):
                    z.writestr(generic+'-armeabi-v7a',binaries['arm32'])
                if name=='arch-unsupported':z.writestr(generic+'-x86',binaries['generic'])
                if name in ['bad-compatibility','valid-compatibility']:
                    compatibility=io.BytesIO()
                    with zipfile.ZipFile(compatibility,'w') as inner:inner.writestr('manifest.xml','<manifest/>')
                    z.writestr('compatibility.zip',b'not a zip' if name=='bad-compatibility' else compatibility.getvalue())
                if name=='file-contexts':z.writestr('file_contexts',b'/fixture u:object_r:fixture:s0\n')
                z.writestr('dummy.txt',b'unchanged signature-covered content')
            payload=buf.getvalue()
            if name.startswith('signed-'):payload=sign(payload)
            if name=='signed-tampered':payload=payload.replace(b'unchanged signature-covered content',b'Xnchanged signature-covered content',1)
            if name=='truncated-zip':payload=payload[:-30]
            package=jail/'packages/test.zip';package.write_bytes(payload)
            if name.startswith('digest-') and name!='digest-missing':
                hexdigest=hashlib.md5(payload).hexdigest() if name=='digest-md5-good' else hashlib.sha256(payload).hexdigest()
                if name=='digest-bad':hexdigest='0'*64
                content='not a checksum' if name=='digest-malformed' else hexdigest+'  '+('other.zip' if name=='digest-wrong-name' else 'test.zip')+'\n'
                package.with_name('test.zip.md5' if name=='digest-md5-good' else 'test.zip.sha256').write_text(content)
            if name=='extract-open-error':(jail/'tmp/updater').mkdir()
            if name=='target-missing-lib':(jail/'android/system/lib64/libc.so').unlink()
            run=subprocess.run(['chroot',str(jail),'/test',name,str(int(name in positive))],capture_output=True,text=True,timeout=20)
            output=jail/'packages/result.txt';tag=output.read_text().strip() if output.is_file() else None
            expected_tag='arm64' if name in ['arch-first','arch-abi-property','arch-both','arch-empty-fallback'] else 'arm32' if name in ['arch-second','arch-reversed'] else 'generic'
            content_ok=(tag==expected_tag) if name in positive else not output.exists()
            contexts=jail/'file_contexts'
            contexts_ok=(contexts.is_file() and contexts.read_bytes()==b'/fixture u:object_r:fixture:s0\n') if name=='file-contexts' else not contexts.exists()
            passed=run.returncode==0 and content_ok and contexts_ok
            extra={}
            if target:
                extracted=jail/'tmp/updater'
                if name in ['arch-none','arch-unsupported','signed-wrong-key','signed-tampered','digest-bad']:
                    extra['payload_exact']=not extracted.exists()
                elif name=='extract-open-error':
                    extra['payload_exact']=extracted.is_dir()
                else:
                    selected=('undefined' if name=='target-link-failure' else 'arm64' if name in
                              ['arch-first','arch-both','arch-empty-fallback'] else 'generic')
                    extra['payload_exact']=extracted.is_file() and extracted.read_bytes()==binaries[selected]
                if name=='target-link-failure':extra['linker_rejection']='cannot locate symbol "dijun_updater_missing_symbol"' in run.stderr
                if name=='target-missing-lib':extra['linker_rejection']='libc.so' in run.stderr and 'not found' in run.stderr
                marker=jail/'packages/target-entered.txt'
                entered=name in positive or name in ['updater-nonzero','updater-badprogress','target-signal','target-partial-failure']
                extra['target_main']=marker.is_file() and marker.read_bytes()==b'ARM64 constructor=41 api=3 zip=/packages/test.zip\n' if entered else not marker.exists()
                statuses=[int(v) for v in re.findall(r'target_wait_status=(\d+)',run.stdout)]
                if entered:
                    expected_status=(7<<8 if name in ['updater-nonzero','target-partial-failure'] else 15 if name=='target-signal' else 0)
                    extra['wait_status']=statuses==[expected_status]
                    if name in positive:
                        fraction='0.375' if name=='signed-correct' else '0.5'
                        extra['progress_pipe']=('target_show_progress='+fraction+',1\n' in run.stdout and
                                                'target_progress=1\n' in run.stdout)
                elif name in ['target-link-failure','target-missing-lib']:
                    extra['wait_status']=len(statuses)==1 and statuses[0]!=0
                else:extra['wait_status']=not statuses
                if name=='target-partial-failure':
                    partial=jail/'packages/partial.txt'
                    extra['partial_effect_preserved']=partial.is_file() and partial.read_bytes()==b'partial ARM64 side effect\n' and 'wipe_cache=1' in run.stdout
                passed=passed and all(extra.values())
            cases.append(dict(case=name,status='PASS' if passed else 'FAIL',exit=run.returncode,input_sha256=sha(package),
                              result_tag=tag,expected_tag=expected_tag if name in positive else None,
                              content_ok=content_ok,contexts_ok=contexts_ok,target_checks=extra,output=run.stdout+run.stderr))
            print(cases[-1]['status'],name,flush=True)
            if not passed:print((run.stdout+run.stderr)[-1800:],flush=True)
    bound=[args.source,SRC/'twrpinstall/installcommand.cpp',SRC/'twrp_functions.cpp',SRC/'digest/twrp_digest_driver.cpp',
           Path(__file__).resolve(),ROOT/'tests/zip_install_chain_test.cpp',ROOT/'tests/zip_install_fixture.cpp',ROOT/'tests/nested_partition_path_test.py',*library]
    bound+=list((SRC/'twrpinstall/include').rglob('*.h'))+list((SRC/'otautil/include').rglob('*.h'))
    bound+=list(archive.glob('*.h'))+list((archive/'include').rglob('*.h'))+list((archive/'incfs_support/include').rglob('*.h'))
    bound+=list((SRC/'digest').glob('*.hpp'))
    if target:
        bound+=target.files
        bound += [ROOT/'scripts/firmware_facts.py',ROOT/'scripts/acquire_firmware.py']
    report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,
                sources={str(p):sha(p) for p in bound},binary_dependencies={str(crypto):sha(crypto),str(clang):sha(clang),**dependencies},
                compile_command=cmd,key_operations=transcripts)
    if target:
        report['scope']='Original host ZIP install chain with genuine ARM64 payloads. '+target.metadata()['scope']
        report['target']=target.metadata()
        report['binary_dependencies'].update(target.dependencies)
    destination=args.report
    if target and destination==ROOT/'logs/zip-install-chain.json':destination=ROOT/'logs/zip-install-arm64.json'
    destination.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
