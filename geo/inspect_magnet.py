#!/bin/env python2
import sys
import rootpy.ROOT as r
f = r.TFile.Open(sys.argv[1])
fGeo = f.FAIRGeom
fGeo.GetVolume("MuonShieldArea").Draw("ogl")
r.gPad.SaveAs("shield.eps")

