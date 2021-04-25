#!/usr/bin/env python3
# --------------------( LICENSE                           )--------------------
# Copyright (c) 2014-2021 Beartype authors.
# See "LICENSE" for further details.

'''
Project-wide **Python interpreter version utilities**.

This private submodule is *not* intended for importation by downstream callers.
'''

# ....................{ IMPORTS                           }....................
from sys import version_info

# See the "beartype.cave" submodule for further commentary.
__all__ = ['STAR_IMPORTS_CONSIDERED_HARMFUL']

# ....................{ CONSTANTS ~ at least              }....................
IS_PYTHON_AT_LEAST_4_0 = version_info >= (4, 0)
'''
``True`` only if the active Python interpreter targets at least Python 4.0.0.
'''


#FIXME: After dropping Python 3.9 support:
#* Refactor all code conditionally testing this global to be unconditional.
#* Remove this global.
IS_PYTHON_AT_LEAST_3_10 = IS_PYTHON_AT_LEAST_4_0 or version_info >= (3, 10)
'''
``True`` only if the active Python interpreter targets at least Python 3.10.0.
'''


#FIXME: After dropping Python 3.8 support:
#* Refactor all code conditionally testing this global to be unconditional.
#* Remove this global.
IS_PYTHON_AT_LEAST_3_9 = IS_PYTHON_AT_LEAST_3_10 or version_info >= (3, 9)
'''
``True`` only if the active Python interpreter targets at least Python 3.9.0.
'''


#FIXME: After dropping Python 3.7 support:
#* Refactor all code conditionally testing this global to be unconditional.
#* Remove this global.
IS_PYTHON_AT_LEAST_3_8 = IS_PYTHON_AT_LEAST_3_9 or version_info >= (3, 8)
'''
``True`` only if the active Python interpreter targets at least Python 3.8.0.
'''


#FIXME: After dropping Python 3.6 support:
#* Refactor all code conditionally testing this global to be unconditional.
#* Remove this global.
IS_PYTHON_AT_LEAST_3_7 = IS_PYTHON_AT_LEAST_3_8 or version_info >= (3, 7)
'''
``True`` only if the active Python interpreter targets at least Python 3.7.0.
'''


#FIXME: After dropping Python 3.6 support, *REMOVE* all code conditionally
#testing this global.
IS_PYTHON_3_6 = not IS_PYTHON_AT_LEAST_3_7
'''
``True`` only if the active Python interpreter targets exactly Python 3.6.
'''
