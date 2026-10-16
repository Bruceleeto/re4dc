RE4 Dreamcast test 15, source SHA_PLACEHOLDER

See Known Issues: https://github.com/lamb2k/re4dc/blob/dreamcast-port/port/dreamcast/docs/KNOWN_ISSUES.md

Extract the gdemu folder and copy its four disc files into a new numbered
folder on your GDEMU SD card. Flycast can open gdemu/disc.gdi directly (if
menu or popup text looks broken in Flycast, use its per-pixel renderer
setting).

New disc format: from test 15 the disc is a standard GD-ROM image, laid
out the way the community tool mkdcdisc writes one and pressed GD-ROMs are:
the full-size data track (track03.bin is about 1.2 GB, about 213 MB more
than test 14 on the SD card), the table of contents real GD-ROMs carry, and
the program as the last file. Users reported freezes and crashes on GDEMU
only (#27); a GDEMU console test of the test 14 game in this format ran
fine. Please replace the old folder (don't mix test 14 and test 15 track
files), and if your card manager offers "Shrink GDI", leave it off.

RELEASE_NOTES_PLACEHOLDER (the release coordinator writes "New in test 15"
here from TEST15-SCOPE.md; t15-package.sh refuses to package while this line
is present)

Please tell us about any crash, freeze or missing texture, and where. Photos
help a lot. If you play from a loader other than GDEMU (MODE, USB-GDROM,
DreamShell), please tell us which one and its version.

Source: https://github.com/lamb2k/re4dc/commit/SHA_PLACEHOLDER
