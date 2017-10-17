

def ParseParams(params_string):
    return [float(x) for x in params_string.strip('[]').split(',')]

def StripFixedParams(point):
    return point[2:8] + point[20:]

def CreateDiscreteSpace():
    dZgap = 10
    zGap = dZgap / 2  # halflengh of gap
    return Space(6 * [
                Integer(170 + zGap, 300 + zGap)  # magnet lengths
                ] + 6 * (
                2 * [
                    Integer(10, 100)  # dXIn, dXOut
                ] + 2 * [
                    Integer(20, 200)  # dYIn, dYOut
                ] + 2 * [
                    Integer(2, 70)  # gapIn, gapOut
                ]))

def AddFixedParams(point):
    return FIXED_PARAMS[:2] + point[:6] + FIXED_PARAMS[2:] + point[6:]