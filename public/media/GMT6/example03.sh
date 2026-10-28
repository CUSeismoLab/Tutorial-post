#!/bin/sh
# extract data ignoring header, in order : lon, lat, depth, residual
awk 'NR>1 {print $9,$8,$10,$7}' banda_arc_catalog.txt > extracted.txt

gmt begin section png
gmt makecpt -Cseis -T0/3/0.1 -D -Z -H > res.cpt

gmt subplot begin 3x2 -Fs14c/7c -A
gmt subplot set 0 # transect along lon = 118
# project the data within 0.5 degree onto plane
# output file in order: latitude , depth , residual
gmt project extracted.txt -C118/-12 -E118/-6 -Lw -W-0.5/0.5 -Fyz > projected_input.txt
gmt plot projected_input.txt -JX14c/-7c -R-12/-6/0/650 -BWesn -Bya200f40+l"Depth (km)" -Bxa2f0.5 -Sc4p -W0.5p -Cres.cpt # ploting
echo "lon = 118" | gmt text -F+cBL+f12p,4,black -Dj1c/1c # adding text

gmt subplot set 1 # transect along lon = 120
# project the data within 0.5 degree onto plane
# output file in order: latitude , depth , residual
gmt project extracted.txt -C120/-12 -E120/-6 -Lw -W-0.5/0.5 -Fyz > projected_input.txt
gmt plot projected_input.txt -JX14c/-7c -R-12/-6/0/650 -BwEsn -Bya200f40 -Bxa2f0.5 -Sc4p -W0.5p -Cres.cpt # ploting
echo "lon = 120" | gmt text -F+cBL+f12p,4,black -Dj1c/1c # adding text

gmt subplot set 2 # transect along lon = 122.5
# project the data within 0.5 degree onto plane
# output file in order: latitude , depth , residual
gmt project extracted.txt -C122.5/-12 -E122.5/-6 -Lw -W-0.5/0.5 -Fyz > projected_input.txt
gmt plot projected_input.txt -JX14c/-7c -R-12/-6/0/650 -BWesn -Bya200f40+l"Depth (km)" -Bxa2f0.5 -Sc4p -W0.5p -Cres.cpt # ploting
echo "lon = 122.5" | gmt text -F+cBL+f12p,4,black -Dj1c/1c # adding text

gmt subplot set 3 # transect along lon = 124.0
# project the data within 0.5 degree onto plane
# output file in order: latitude , depth , residual
gmt project extracted.txt -C124.0/-12 -E124.0/-6 -Lw -W-0.5/0.5 -Fyz > projected_input.txt
gmt plot projected_input.txt -JX14c/-7c -R-12/-6/0/650 -BwEsn -Bya200f40 -Bxa2f0.5 -Sc4p -W0.5p -Cres.cpt # ploting
echo "lon = 124.0" | gmt text -F+cBL+f12p,4,black -Dj1c/1c # adding text

gmt subplot set 4 # transect along lon = 125.5
# project the data within 0.5 degree onto plane
# output file in order: latitude , depth , residual
gmt project extracted.txt -C125.5/-12 -E125.5/-6 -Lw -W-0.5/0.5 -Fyz > projected_input.txt
gmt plot projected_input.txt -JX14c/-7c -R-12/-6/0/650 -BWeSn -Bya200f40+l"Depth (km)" -Bxa2f0.5 -Sc4p -W0.5p -Cres.cpt # ploting
echo "lon = 125.5" | gmt text -F+cBL+f12p,4,black -Dj1c/1c # adding text

gmt subplot set 5 # transect along lon = 128.0
# project the data within 0.5 degree onto plane
# output file in order: latitude , depth , residual
gmt project extracted.txt -C128.0/-12 -E128.0/-6 -Lw -W-0.5/0.5 -Fyz > projected_input.txt
gmt plot projected_input.txt -JX14c/-7c -R-12/-6/0/650 -BwESn -Bya200f40 -Bxa2f0.5 -Sc4p -W0.5p -Cres.cpt # ploting
echo "lon = 128.0" | gmt text -F+cBL+f12p,4,black -Dj1c/1c # adding text

gmt subplot end

gmt colorbar -DJBC+e+w8c+o1c -Cres.cpt -Bxa1+L"RMS residuals (s)"
gmt end
