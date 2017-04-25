#!/bin/env python2
import sys
import rootpy.ROOT as r
f = r.TFile.Open(sys.argv[1])
fGeo = f.FAIRGeom
fGeo.GetVolume("MuonShieldArea").Draw("ogl")
# fGeo.GetVolume("MuonShieldArea").GetNode("MagnAbsorb1_1").VisibleDaughters(False)
# fGeo.GetVolume("MuonShieldArea").GetNode("MagnAbsorb1_1").SetVisibility(False)
# fGeo.GetVolume("MuonShieldArea").GetNode("MagnAbsorb2_1").VisibleDaughters(False)
# fGeo.GetVolume("MuonShieldArea").GetNode("MagnAbsorb2_1").SetVisibility(False)
