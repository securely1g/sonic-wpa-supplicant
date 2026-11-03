"""Exercise the actual Make C++ flag bridge without compiling or packaging."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    make, rules = [Path(value).absolute() for value in sys.argv[1:]]
    baseline = '-O2 -isystem /declared/include -D_FORTIFY_SOURCE=3 -Wl,-z,now'
    suffix = '-Iowner -D_FORTIFY_SOURCE=4 -Ilast'
    cases = [
        ('native', '', baseline, suffix, baseline + ' ' + suffix),
        ('bazel', baseline, baseline, suffix, suffix),
        ('prefix', baseline, '-DFIRST ' + baseline, suffix, '-DFIRST  ' + suffix),
        ('missing', baseline, '-O0', suffix, None),
        ('duplicate', baseline, baseline + ' ' + baseline, suffix, None),
    ]
    with tempfile.TemporaryDirectory(dir=os.environ.get('TEST_TMPDIR')) as temporary:
        root = Path(temporary)
        for name, selected, initial, later, expected in cases:
            result = root / (name + '.flags')
            build = root / (name + '.mk')
            build.write_text('CFLAGS = ' + initial + '\nWPA_CXX_BASE_CFLAGS = ' + selected +
                             '\ninclude ' + str(rules) + '\nCFLAGS += ' + later +
                             '\n.PHONY: check\ncheck:\n\t$(file >' + str(result) + ',$(_wpa_cxx_cflags))\n\t@:\n')
            process = subprocess.run([make, '--no-print-directory', '-f', build, 'check'],
                                     cwd=root, capture_output=True, text=True)
            if expected is None:
                assert process.returncode != 0 and 'baseline must occur exactly once' in process.stderr, (name, process)
            else:
                assert process.returncode == 0, (name, process.stderr)
                assert result.read_text().strip() == expected, (name, result.read_text(), expected)
    print('Native flags, ordered owner additions, and missing/ambiguous baseline rejection passed')


if __name__ == '__main__':
    main()
