#!/usr/bin/env python
"""
Generate lobatto.pyx file.
"""
import sys
sys.path.append('.')
import os
from optparse import OptionParser

import sympy as sm
import numpy as nm
import matplotlib.pyplot as plt

from sfepy import top_dir
from sfepy.base.ioutils import InDir

cdef = """
cdef float64 %s(float64 x):
    return %s
"""

fun_list = """
cdef fun %s[%d]

%s[:] = [%s]
"""

def gen_lobatto(max_order):
    assert max_order > 2

    x = sm.symbols('x')

    lobs = [0, 1]
    lobs[0] = (1 - x) / 2
    lobs[1] = (1 + x) / 2

    dlobs = [lob.diff('x') for lob in lobs]

    legs = [sm.legendre(0, 'y')]
    clegs = [sm.ccode(legs[0])]
    dlegs = [sm.legendre(0, 'y').diff('y')]
    cdlegs = [sm.ccode(dlegs[0])]

    clobs = [sm.ccode(lob) for lob in lobs]
    cdlobs = [sm.ccode(dlob) for dlob in dlobs]

    denoms = [] # for lobs.

    for ii in range(2, max_order + 1):
        coef = sm.sympify('sqrt(2 * (2 * %s - 1)) / 2' % ii)
        leg = sm.legendre(ii - 1, 'y')

        pleg = leg.as_poly()
        coefs = pleg.all_coeffs()
        denom = max(sm.denom(val) for val in coefs)

        cleg = sm.ccode(sm.horner(leg*denom)/denom)

        dleg = leg.diff('y')
        cdleg = sm.ccode(sm.horner(dleg*denom)/denom)

        lob = sm.simplify(coef * sm.integrate(leg, ('y', -1, x)))
        lobnc = sm.simplify(sm.integrate(leg, ('y', -1, x)))

        plobnc = lobnc.as_poly()
        coefs = plobnc.all_coeffs()
        denom = sm.denom(coef) * max(sm.denom(val) for val in coefs)

        clob = sm.ccode(sm.horner(lob*denom)/denom)

        dlob = lob.diff('x')
        cdlob = sm.ccode(sm.horner(dlob*denom)/denom)

        legs.append(leg)
        clegs.append(cleg)
        dlegs.append(dleg)
        cdlegs.append(cdleg)
        lobs.append(lob)
        clobs.append(clob)
        dlobs.append(dlob)
        cdlobs.append(cdlob)
        denoms.append(denom)

    coef = sm.sympify('sqrt(2 * (2 * %s - 1)) / 2' % (max_order + 1))
    leg = sm.legendre(max_order, 'y')

    pleg = leg.as_poly()
    coefs = pleg.all_coeffs()
    denom = max(sm.denom(val) for val in coefs)

    cleg = sm.ccode(sm.horner(leg*denom)/denom)

    dleg = leg.diff('y')
    cdleg = sm.ccode(sm.horner(dleg*denom)/denom)

    legs.append(leg)
    clegs.append(cleg)
    dlegs.append(dleg)
    cdlegs.append(cdleg)

    kerns = []
    ckerns = []
    dkerns = []
    cdkerns = []
    for ii, lob in enumerate(lobs[2:]):
        kern = sm.simplify(lob / (lobs[0] * lobs[1]))
        dkern = kern.diff('x')

        denom = denoms[ii] / 4
        ckern = sm.ccode(sm.horner(kern*denom)/denom)
        cdkern = sm.ccode(sm.horner(dkern*denom)/denom)

        kerns.append(kern)
        ckerns.append(ckern)
        dkerns.append(dkern)
        cdkerns.append(cdkern)

    return (legs, clegs, dlegs, cdlegs,
            lobs, clobs, dlobs, cdlobs,
            kerns, ckerns, dkerns, cdkerns,
            denoms)

def plot_polys(fig, polys, var_name='x'):
    plt.figure(fig)
    plt.clf()

    x = sm.symbols(var_name)
    vx = nm.linspace(-1, 1, 100)

    for ii, poly in enumerate(polys):
        print ii
        print poly
        print poly.as_poly(x).all_coeffs()

        vy = [float(poly.subs(x, xx)) for xx in vx]
        plt.plot(vx, vy)

def append_polys(out, cpolys, comment, cvar_name, var_name='x', shift=0):
    names = []
    out.append('\n# %s functions.\n' % comment)
    for ii, cpoly in enumerate(cpolys):
        name = '%s_%03d' % (cvar_name, ii + shift)
        function = cdef % (name, cpoly.replace(var_name, 'x'))
        out.append(function)
        names.append(name)

    return names

def append_lists(out, names, length):
    args = ', '.join(['&%s' % name for name in names])
    name = names[0][:-4]
    _list = fun_list % (name, length, name, args)
    out.append(_list)

usage = """%prog [options]

Generate lobatto.pyx file.
"""
help = {
    'max_order' :
    'maximum order of polynomials [default: %default]',
    'plot' :
    'plot polynomials',
}

def main():
    parser = OptionParser(usage=usage, version='%prog')
    parser.add_option('-m', '--max-order', metavar='order', type=int,
                      action='store', dest='max_order',
                      default=10, help=help['max_order'])
    parser.add_option('', '--plot',
                      action='store_true', dest='plot',
                      default=False, help=help['plot'])
    options, args = parser.parse_args()

    max_order = options.max_order

    (legs, clegs, dlegs, cdlegs,
     lobs, clobs, dlobs, cdlobs,
     kerns, ckerns, dkerns, cdkerns,
     denoms) = gen_lobatto(max_order)

    if options.plot:
        plot_polys(1, lobs)
        plot_polys(11, dlobs)

        plot_polys(2, kerns)
        plot_polys(21, dkerns)

        plot_polys(3, legs, var_name='y')
        plot_polys(31, dlegs, var_name='y')

        plt.show()

    indir = InDir(os.path.join(top_dir, 'sfepy/fem/extmods/'))
    fd = open(indir('lobatto_template.pyx'), 'r')
    template = fd.read()
    fd.close()

    filename = indir('lobatto.pyx')

    fd = open(filename, 'w')

    out = []

    names_lobatto = append_polys(out, clobs,
                                 'Lobatto', 'lobatto')
    names_d_lobatto = append_polys(out, cdlobs,
                                   'Derivatives of Lobatto', 'd_lobatto')

    names_kernel = append_polys(out, ckerns,
                                'Kernel', 'kernel',
                                shift=2)
    names_d_kernel = append_polys(out, cdkerns,
                                  'Derivatives of kernel', 'd_kernel',
                                  shift=2)

    names_legendre = append_polys(out, clegs,
                                  'Legendre', 'legendre',
                                  var_name='y')
    names_d_legendre = append_polys(out, cdlegs,
                                    'Derivatives of Legendre', 'd_legendre',
                                    var_name='y')

    out.append('\n# Lists of functions.\n')

    out.append('\ncdef int32 max_order = %d\n' % max_order)

    append_lists(out, names_lobatto, max_order + 1)
    append_lists(out, names_d_lobatto, max_order + 1)

    append_lists(out, names_kernel, max_order - 1)
    append_lists(out, names_d_kernel, max_order - 1)

    append_lists(out, names_legendre, max_order + 1)
    append_lists(out, names_d_legendre, max_order + 1)

    fd.write(template.replace('REPLACE_TEXT', ''.join(out)))

    fd.close()

if __name__ == '__main__':
    main()
