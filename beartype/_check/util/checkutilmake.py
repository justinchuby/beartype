#!/usr/bin/env python3
# --------------------( LICENSE                            )--------------------
# Copyright (c) 2014-2022 Beartype authors.
# See "LICENSE" for further details.

'''
**Beartype type-checking function code utility factories** (i.e., low-level
callables dynamically generating pure-Python code snippets type-checking
arbitrary objects passed to arbitrary callables against PEP-compliant type hints
passed to those same callables).

This private submodule is *not* intended for importation by downstream callers.
'''

# ....................{ IMPORTS                            }....................
from beartype.typing import Callable
from beartype._check.checkmagic import (
    ARG_NAME_GETRANDBITS,
)
from beartype._check.util._checkutilsnip import (
    CODE_SIGNATURE_ARG,
    CODE_INIT_RANDOM_INT,
)
from beartype._data.datatyping import (
    LexicalScope,
)
from beartype._util.text.utiltextrepr import represent_object

# ....................{ MAKERS ~ signature                 }....................
#FIXME: Unit test us up, please.
def make_func_signature(
    # Mandatory parameters.
    func_name: str,
    func_scope: LexicalScope,
    code_signature_format: str,

    # Optional parameters.
    code_signature_prefix: str = '',
    is_debug: bool = False,

    # String globals required only for their bound str.format() methods.
    CODE_SIGNATURE_ARG_format: Callable = (
        CODE_SIGNATURE_ARG.format),
) -> str:
    '''
    **Type-checking signature factory** (i.e., low-level function dynamically
    generating and returning the **signature** (i.e., callable declaration
    prefixing the body of that callable) of a callable type-checking arbitrary
    objects against arbitrary PEP-compliant type hints to be subsequently
    defined, described by the passed parameters.

    Parameters
    ----------
    func_name : str
        Unqualified basename of the callable declared by this signature.
    func_scope : LexicalScope
        **Local scope** (i.e., dictionary mapping from the name to value of
        each hidden parameter declared in this signature) of that callable,
        where a "hidden parameter" is a parameter whose name is prefixed by
        ``"__beartype_"`` and whose value is that of an external attribute
        internally referenced in the body of that callable.
    code_signature_format : str
        Code snippet declaring the unformatted signature of that callable, which
        this factory then formats by replacing these format variables in this
        code snippet:

        * ``{func_name}``, replaced by the value of the ``func_name`` parameter.
        * ``{code_signature_prefix}``, replaced by the value of the
          ``code_signature_prefix`` parameter.
        * ``{code_signature_args}``, replaced by the declaration of all hidden
          parameters in the passed ``func_scope`` parameter.
    code_signature_prefix : str, optional
        Code snippet prefixing this signature, typically either:

        * For synchronous callables, the empty string.
        * For asynchronous callables (e.g., asynchronous generators,
          coroutines), the space-suffixed keyword ``"async "``.

        Defaults to the empty string and thus synchronous behaviour.
    is_debug : bool, optional
        ``True`` only if enabling debug-specific output. Defaults to ``False``.
        Specifically, enabling this parameter instructs this factory to:

        * Append to the declaration of each such hidden parameter the
          machine-readable representation of the initial value of that
          parameter, stripped of newlines and truncated to a hopefully sensible
          length. Since the :func:`represent_object` function called below to
          sanitize that value is incredibly slow, these substrings are
          conditionally embedded in the returned signature *only* when enabling
          debug-specific output.

    Yields
    ----------
    str
        Signature of this callable.
    '''
    assert isinstance(func_name, str), f'{repr(func_name)} not string.'
    assert isinstance(func_scope, dict), f'{repr(func_scope)} not dictionary.'
    assert isinstance(is_debug, bool), f'{repr(is_debug)} not boolean.'

    # Python code snippet declaring all optional private beartype-specific
    # parameters directly derived from the local scope established by the above
    # calls to the _code_check_args() and _code_check_return() functions.
    code_signature_args = ''

    # For the name and value of each such parameter...
    for arg_name, arg_value in func_scope.items():
        # Machine-readable representation of this parameter's initial value,
        # stripped of newline and truncated to a (hopefully) sensible length.
        # Since the represent_object() function called below to sanitize this
        # value is incredibly slow, this representation is conditionally
        # appended as a human-readable comment to the declaration of this
        # parameter below *ONLY* if the caller explicitly requested debugging.
        arg_comment = (
            f' # is {represent_object(arg_value)}'
            if is_debug else
            ''
        )

        # Compose the declaration of this parameter in the signature of this
        # wrapper from...
        code_signature_args += CODE_SIGNATURE_ARG_format(
            arg_name=arg_name,
            arg_comment=arg_comment,
        )

    #FIXME: *YIKES.* We need to pass a unique tester function signature here
    #resembling:
    #    def {{func_name}}(obj: object) -> bool:
    #To do so sanely, let's generalize this factory to accept an additional
    #mandatory "func_signature" parameter, please. We'll need to note in the
    #docstring exactly what format variables that parameter is expected to
    #contain, of course.

    # Python code snippet declaring the signature of this wrapper.
    code_signature = code_signature_format.format(
        func_name=func_name,
        code_signature_prefix=code_signature_prefix,
        code_signature_args=code_signature_args,
    )

    # Python code snippet of preliminary statements (e.g., local variable
    # assignments) if any *AFTER* generating snippets type-checking parameters
    # and returns (which modifies dataclass variables tested below).
    code_body_init = (
        # If the body of this wrapper requires a pseudo-random integer, append
        # code generating and localizing such an integer to this signature.
        CODE_INIT_RANDOM_INT
        if ARG_NAME_GETRANDBITS in func_scope else
        # Else, this body requires *NO* such integer. In this case, preserve
        # this signature as is.
        ''
    )

    # Return this signature suffixed by zero or more preliminary statements.
    return (
        f'{code_signature}'
        f'{code_body_init}'
    )
