#!/usr/bin/env python3
"""Exercise image-target taps through the original router and LVGL page host.

The target chooser is rendered and selected; REPLACE, POP back to the install
entry, and PUSH back to confirmation execute in the real page host/router. The
install-source and manager/backend operations remain fixtures; Android input,
fonts, persistence and physical hardware are not tested.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from haptics_ui_test import ROOT, SRC, LVGL, lvgl_library, extract, sha

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=__import__('pathlib').Path)
    parser.add_argument('--report',type=__import__('pathlib').Path,default=ROOT/'logs/install-target-interaction.json')
    args=parser.parse_args()
    flags=ROOT/'dtsrc/O1_asic_dual/profiles/common/root/system/etc/twrp.flags'
    text=flags.read_text()
    image_sha=None
    if args.image:
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from verify_devicefix import entries
        raw,archive=entries(args.image)
        assert archive['system/etc/twrp.flags'][-1]==flags.read_bytes()
        image_sha=hashlib.sha256(raw).hexdigest()
    library, provenance = lvgl_library()
    production = ['pages/install_confirm_page.cpp', 'components/check_row.cpp', 'components/flat_button.cpp', 'components/section_label.cpp', 'components/tip_card.cpp', 'components/swipe_slider.cpp', 'components/setting_card.cpp',
                  'components/icon.cpp', 'core/ui_event_guard.cpp', 'core/ui_helpers.cpp',
                  'core/ui_metrics.cpp', 'shell/page_host.cpp', 'shell/page_scaffold.cpp',
                  'shell/navigation_fade.cpp', 'pages/page_router.cpp',
                  'gui2_svg_cache.cpp', 'i18n/en.cpp']
    sources = [SRC/name for name in production]
    with tempfile.TemporaryDirectory(prefix='install-target-interaction-') as tmp:
        from pathlib import Path
        temp = Path(tmp)
        android=SRC.parents[2]
        base=android/'system/libbase'
        host=android/'out/host/linux-x86/lib64'
        clang=android/'prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++'
        parser_cpp=temp/'parser.cpp'
        parser_cpp.write_text("""
#include <cassert>
#include <iostream>
#include "fstab_parser.hpp"
int main(int argc,char**argv){
 assert(argc==2);auto parsed=twrp::fstab::ParseTwrpFlagsFromFile(argv[1]);
 assert(parsed.Ok()&&parsed.skipped_lines==0&&parsed.unknown_flags==0&&parsed.fstab.size()==11);
 int restricted=0;
 for(const auto&e:parsed.fstab){
  if(!e.twrp_flags.flashimg){
   assert(e.twrp_flags.wipeingui==0&&!e.fs_mgr_flags.formattable);
   ++restricted;continue;
  }
  assert(e.fs_type=="emmc"&&e.twrp_flags.flashimg&&e.twrp_flags.backup==1&&e.fs_mgr_flags.slot_select);
  assert(e.blk_device=="/dev/block/by-name"+e.mount_point);
  assert(!e.twrp_flags.storage&&!e.twrp_flags.wipeingui&&!e.fs_mgr_flags.formattable);
  std::cout<<e.mount_point<<'\\t'<<e.twrp_flags.display<<'\\n';
 }
 assert(restricted==6);
}
""")
        parser_cmd=[str(clang),'-std=c++23','-stdlib=libc++','-I'+str(SRC.parent/'fstab'),
                    '-I'+str(base/'include'),str(parser_cpp),str(SRC.parent/'fstab/fstab_parser.cpp'),
                    '-L'+str(host),'-Wl,-rpath,'+str(host),'-lbase','-llog','-o',str(temp/'parse')]
        subprocess.run(parser_cmd,check=True)
        rows=[line.split('\t') for line in subprocess.check_output([str(temp/'parse'),str(flags)],text=True).splitlines()]
        assert {p for p,n in rows}=={'/boot','/init_boot','/vendor_boot','/recovery','/dtbo'}
        (temp/'image-targets.inc').write_text('static std::vector<gui2_backend::image_target> install_targets={'+
            ','.join('{'+json.dumps(n)+','+json.dumps(p)+',true}' for p,n in rows)+'};\n')
        gui = (SRC/'gui2.cpp').read_text()
        (temp/'callback.inc').write_text(extract(gui, 'install_target_event_cb'))
        artwork = SRC/'image/ic_arrow_right.svg'
        assert artwork.is_file()
        (temp/'gui2_svg_assets.h').write_bytes(subprocess.check_output(
            ['python3', str(SRC/'generate_svg_header.py'), str(artwork),str(SRC/'image/ic_slider_arrow.svg')]))
        command = ['g++', '-std=c++20', '-O1', '-g', '-fsanitize=undefined',
                   '-fno-sanitize-recover=undefined', '-DLV_CONF_INCLUDE_SIMPLE',
                   '-DLV_LVGL_H_INCLUDE_SIMPLE', '-DTW_FRAMERATE=120',
                   '-I'+str(temp), '-I'+str(SRC), '-I'+str(LVGL),
                   str(ROOT/'tests/install_target_interaction_test.cpp'), *map(str, sources),
                   str(library), '-lpthread', '-lm', '-o', str(temp/'test')]
        subprocess.run(command, check=True)
        cases=[]
        for index in range(len(rows)):
            for mode in ['label', 'detail', 'arrow', 'blank', 'drag-out']:
                result = subprocess.run([str(temp/'test'), str(index), mode], capture_output=True,
                                        text=True, timeout=20)
                cases.append(dict(index=index,mode=mode,returncode=result.returncode,
                                  stdout=result.stdout,stderr=result.stderr))
                print(index,mode,'PASS' if result.returncode==0 else 'FAIL',result.stdout+result.stderr,flush=True)
    files=sources+[flags,SRC.parent/'fstab/fstab_parser.cpp',SRC.parent/'fstab/fstab_parser.hpp',SRC/'image/ic_slider_arrow.svg',SRC/'gui2.cpp',artwork,SRC/'generate_svg_header.py',
                   ROOT/'tests/install_target_interaction_test.cpp',ROOT/'tests/install_target_interaction_test.py']
    # Headers participating in the host compilation are bound separately from LVGL.
    files += sorted({h for p in sources for h in p.parent.glob('*.h')})
    report=dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',
                scope=__doc__,image_sha256=image_sha,parser_rows=rows,parser_compile_command=parser_cmd,cases=cases,sources={str(p):sha(p) for p in files},lvgl=provenance)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
