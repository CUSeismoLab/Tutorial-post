#!/bin/sh

gmt begin Banda_Arc_Region06 png

# constructing the frame
gmt basemap -JM10c -R114/131/-14/-5 -BWeSn -Bxa5f1 -Bya2f1
# creating a colormap with customized boundaries
gmt makecpt -Crelief -T-6000/6000/200 -D -Z -H > elevation.cpt
# plotting the topography data, which can be remotely obtained from gmt database using the @earth_relief_??? option
gmt grdimage @earth_relief_01m -Celevation.cpt -I+
# plotting the coastline data
gmt coast -W0.5p,black -Da
# inset a global figure with the specify boundary
gmt inset begin -Dn1/0+jBR+w2.5c
gmt coast -Rg -JG123/-10/90/? -B -Swhite -A5000 -Ggray -W0.2p,black -Da --MAP_FRAME_PEN=0.2p
echo -e "\n114 -14\n131 -14\n131 -5\n114 -5\n114 -14" | gmt plot -W0.5p,red
gmt inset end
# plotting the trench data using given data file
gmt plot java_trench.txt -W1p,white
# inserting text
echo '116 -12 Java trench' | gmt text -F+f8p,white
# extracting stations locations from data files
awk 'NR>1 {print $5,$6}' GE_3_stations.txt | gmt plot -Si6p -W0.1p,black -Gcyan
awk -F"|" 'NR>3 {print $6,$5}' YS_30_stations.txt | gmt plot -Si6p -W0.1p,black -Gwhite
# creating colorbar legend
gmt colorbar -Dn1/0+o0.5c/0c+jBL+w5.5c -Bxa3000 -By+l"Topo (m)" -Celevation.cpt

gmt end show

rm elevation.cpt
