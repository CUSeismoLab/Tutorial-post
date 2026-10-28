#!/bin/sh
gmt begin catalog png
# the frame
gmt basemap -JM15c -R115/131/-13/-5 -Bxa5f1 -Bya5f1 -BWeSn+t"Final catalog" --MAP_FRAME_TYPE=plain --FONT_TITLE=10p --MAP_TITLE_OFFSET=-8p
# plotting coastline with specify land and sea colours
gmt coast -Gwhite -Slightblue -W0.1p,black -Da
# creating customized colormaps
gmt makecpt -Chot -T0/400/10 -D -Z -Ic -H > depth.cpt
awk '{print $9,$8,$10}' banda_arc_catalog.txt > catalog.xyz

# plotting the earthquake data
gmt plot catalog.xyz -Sc0.1c -Cdepth.cpt
# plotting the trench
gmt plot java_trench.txt -W1p,black
# extracting station data and plot them
awk 'NR>1 {print $5,$6}' GE_3_stations.txt |gmt psxy -Si7p -W0.01p,black -Gblue
awk -F"|" 'NR>3 {print $6,$5}' YS_30_stations.txt |gmt psxy -Si7p -W0.01p,black -Gblack
# creating a colorbar
gmt colorbar -DjBL+h+o0.3c/0.6c+jBL+w5c/0.3c+e -By+l"Depth (km)" -Bxa100 -Cdepth.cpt
# plotting text
echo "128 -12.5 N = 19074" | gmt text -F+f8p,black
echo "116 -11.5 Java trench" | gmt text -F+f8p,black
gmt end

