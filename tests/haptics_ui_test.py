#!/usr/bin/env python3
"""Run GUI2 widgets and extracted production callbacks with real host LVGL.

LVGL input dispatch, drawing, click guard, flat button, keyboard and swipe slider
are production code. Business operations/settings and the hardware sink are
substitutes; no partition, device or motor is accessed. This is a widget fixture,
not the complete Android recovery UI or DRM display.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
SRC = Path('/root/AAA/twrp/bootable/recovery/gui2')
LVGL = Path('/root/AAA/twrp/external/lvgl')
CALLBACKS = ['sideload_cancel_cb', 'sort_choice_cb', 'install_countdown_cancel_cb',
             'backup_cancel_cb', 'change_fs_choice_event_cb', 'keyboard_feedback_cb',
             'sideload_option_cb']
CASES = ['sideload', 'sort', 'countdown', 'backup', 'filesystem', 'two-taps',
         'drag-out', 'drag-out-back', 'press-lost', 'no-hardware', 'toggle',
         'keyboard', 'keyboard-cancel', 'keyboard-drag-out-back', 'keyboard-two-taps',
         'keyboard-disabled', 'swipe-complete', 'swipe-short',
         'swipe-disabled-mid-drag', 'swipe-stray-release', 'swipe-reenable']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_png(ppm, target):
    # Encode the rendered framebuffer without resizing or repainting it.
    magic, dimensions, maximum, pixels = ppm.read_bytes().split(b'\n', 3)
    width, height = map(int, dimensions.split())
    assert magic == b'P6' and maximum == b'255' and len(pixels) == width*height*3
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    rows = b''.join(b'\0'+pixels[y*width*3:(y+1)*width*3] for y in range(height))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+
                       chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
    return dict(path=str(target.relative_to(ROOT)),sha256=sha(target),width=width,height=height)


def extract(text, name):
    match = re.search(r'^static void '+re.escape(name)+r'\([^;{]*\)\s*\{', text, re.M)
    assert match, f'{name}: missing definition'
    start, opening = match.start(), match.end()-1
    end, depth = opening + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def lvgl_library():
    # Use exactly the source selection in the Android module, plus the actual
    # GUI2 configuration. The host branch naturally disables ARM NEON assembly.
    bp = (LVGL/'Android.bp').read_text()
    patterns = re.findall(r'"([^"]+)"', bp.split('srcs: [', 1)[1].split(']', 1)[0])
    sources = sorted({p for pattern in patterns for p in LVGL.glob(pattern)})
    fingerprints = {str(p): sha(p) for p in sources + sorted(LVGL.rglob('*.h'))}
    for p in [LVGL/'Android.bp', SRC/'lv_conf.h']:
        fingerprints[str(p)] = sha(p)
    compiler = subprocess.check_output(['g++', '--version'], text=True).splitlines()[0]
    flags = f'-O1 -g0 -DLV_CONF_INCLUDE_SIMPLE -DLV_LVGL_H_INCLUDE_SIMPLE -DTW_FRAMERATE=120 -I{LVGL} -I{SRC}'
    key = hashlib.sha256(json.dumps([fingerprints, compiler, flags], sort_keys=True).encode()).hexdigest()
    build = ROOT/'tests/.cache/lvgl'/key
    build.mkdir(parents=True, exist_ok=True)
    library = build/'liblvgl.a'
    if not library.exists():
        rules = ['all: liblvgl.a\n']
        objects = [f'{i}.o' for i in range(len(sources))]
        rules.append('liblvgl.a: ' + ' '.join(objects) + '\n\tar rcs $@ $^\n')
        for obj, source in zip(objects, sources):
            tool = 'g++ -std=c++20' if source.suffix == '.cpp' else 'gcc -std=gnu11'
            rules.append(f'{obj}: {source}\n\t{tool} {flags} -c $< -o $@\n')
        (build/'Makefile').write_text('\n'.join(rules))
        jobs = subprocess.check_output(['nproc'], text=True).strip()
        subprocess.run(['make', '-j'+jobs], cwd=build, check=True)
    return library, {'source_files': fingerprints, 'compiler': compiler,
                     'flags': flags, 'library_sha256': sha(library)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SRC,
                        help='GUI2 source root; an archived root may contain only changed files')
    parser.add_argument('--output', type=Path, default=ROOT/'logs/haptics-ui.json')
    args = parser.parse_args()
    def source(name):
        p = args.source/name
        return p if p.exists() else SRC/name
    gui = source('gui2.cpp')
    methods = '\n\n'.join(extract(gui.read_text(), name) for name in CALLBACKS)
    production = ['core/ui_event_guard.cpp', 'core/ui_helpers.cpp', 'core/ui_metrics.cpp',
                  'components/flat_button.cpp', 'components/keyboard.cpp',
                  'components/swipe_slider.cpp', 'components/icon.cpp', 'gui2_svg_cache.cpp']
    library, lvgl_record = lvgl_library()
    with tempfile.TemporaryDirectory(prefix='dijun-haptics-ui-') as temp:
        temp = Path(temp)
        (temp/'callbacks.inc').write_text(methods)
        artwork = SRC/'image/ic_slider_arrow.svg'
        header = subprocess.check_output(['python3', str(SRC/'generate_svg_header.py'), str(artwork)])
        (temp/'gui2_svg_assets.h').write_bytes(header)
        command = ['g++', '-std=c++20', '-O1', '-g', '-fsanitize=undefined',
                   '-fno-sanitize-recover=undefined', '-DLV_CONF_INCLUDE_SIMPLE',
                   '-DLV_LVGL_H_INCLUDE_SIMPLE', '-DTW_FRAMERATE=120',
                   '-I'+str(temp), '-I'+str(args.source.resolve()), '-I'+str(SRC), '-I'+str(LVGL),
                   str(ROOT/'tests/haptics_ui_test.cpp')]
        command += [str(source(n)) for n in production]
        command += [str(library), '-lpthread', '-lm', '-o', str(temp/'test')]
        subprocess.run(command, check=True)
        cases, frames = [], []
        for case in CASES:
            ppm = temp/(case+'.ppm')
            result = subprocess.run([str(temp/'test'), case, str(ppm)], text=True,
                                    capture_output=True, timeout=20)
            cases.append(dict(case=case, status='PASS' if result.returncode == 0 else 'FAIL',
                              returncode=result.returncode, output=result.stdout+result.stderr))
            print(case, cases[-1]['status'], flush=True)
            if ppm.exists():
                frames.append(save_png(ppm,args.output.resolve().parent/(args.output.stem+'-frames')/(case+'.png')))
        report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',
                      scope=__doc__, cases=cases, lvgl=lvgl_record,
                      sources={str(source(n)):sha(source(n)) for n in production+['gui2.cpp']},
                      headers={str(source(p.relative_to(SRC))):sha(source(p.relative_to(SRC)))
                               for p in sorted(SRC.rglob('*.h'))},
                      configuration={str(SRC/'lv_conf.h'):sha(SRC/'lv_conf.h')},
                      test_sources={str(p):sha(p) for p in [Path(__file__).resolve(), ROOT/'tests/haptics_ui_test.cpp']},
                      artwork={str(artwork):sha(artwork),str(SRC/'generate_svg_header.py'):sha(SRC/'generate_svg_header.py')},
                      callback_names=CALLBACKS,rendered_frames=frames)
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        raise SystemExit(0 if report['status']=='PASS' else 1)


if __name__ == '__main__':
    main()
