#!/usr/bin/env python3
# --------------------( LICENSE                           )--------------------
# Copyright (c) 2014-2021 Beartype authors.
# See "LICENSE" for further details.

'''
**Beartype decorator code generator.**

This private submodule dynamically generates both the signature and body of the
wrapper function type-checking all annotated parameters and return value of the
the callable currently being decorated by the :func:`beartype.beartype`
decorator in a general-purpose manner. For genericity, this relatively
high-level submodule implements *no* support for annotation-based PEPs (e.g.,
:pep:`484`); other lower-level submodules do so instead.

This private submodule is *not* intended for importation by downstream callers.
'''

# ....................{ TODO                              }....................
# All "FIXME:" comments for this submodule reside in this package's "__init__"
# submodule to improve maintainability and readability here.

# ....................{ IMPORTS                           }....................
from beartype.roar import BeartypeDecorParamNameException
from beartype._decor._code.codesnip import (
    ARG_NAME_GETRANDBITS,
    CODE_INIT_ARGS_LEN,
    CODE_INIT_RANDOM_INT,
    CODE_RETURN_UNCHECKED,
    CODE_SIGNATURE,
    PEP484_CODE_CHECK_NORETURN,
)
from beartype._decor._code._pep.pepcode import (
    pep_code_check_param,
    pep_code_check_return,
)
from beartype._decor._data import BeartypeData
from beartype._util.func.arg.utilfuncargiter import (
    ParameterKind,
    iter_func_args,
)
from beartype._util.hint.pep.proposal.pep484585.utilpep484585func import (
    reduce_hint_pep484585_func_return)
from beartype._util.hint.utilhintconv import sanify_hint_root
from beartype._util.hint.utilhinttest import is_hint_ignorable
from beartype._util.text.utiltextlabel import (
    prefix_callable_decorated_param,
    prefix_callable_decorated_return,
)
from beartype._util.text.utiltextmagic import CODE_INDENT_1
from beartype._util.text.utiltextrepr import represent_object
from beartype._util.utilobject import SENTINEL
from collections.abc import Callable
from typing import NoReturn

# See the "beartype.cave" submodule for further commentary.
__all__ = ['STAR_IMPORTS_CONSIDERED_HARMFUL']

# ....................{ CONSTANTS ~ private               }....................
#FIXME: Remove this set *AFTER* handling these kinds of parameters.
_PARAM_KINDS_IGNORABLE = frozenset((
    ParameterKind.POSITIONAL_ONLY,
    ParameterKind.VAR_KEYWORD,
))
'''
Frozen set of all :attr:`ParameterKind` enumeration members to be ignored
during annotation-based type checking in the :func:`beartype.beartype`
decorator.

This includes:

* Constants specific to variadic keyword parameters (e.g., ``**kwargs``), which
  are currently unsupported by :func:`beartype`.
* Constants specific to positional-only parameters, which apply only to
  non-pure-Python callables (e.g., defined by C extensions). The
  :func:`beartype` decorator applies *only* to pure-Python callables, which
  provide no syntactic means for specifying positional-only parameters.
'''

# ....................{ GENERATORS                        }....................
def generate_code(
    data: BeartypeData,

    # "beartype._decor._code.codesnip" string globals required only for their
    # bound "str.format" methods.
    CODE_RETURN_UNCHECKED_format: Callable = CODE_RETURN_UNCHECKED.format,
) -> str:
    '''
    Generate a Python code snippet dynamically defining the wrapper function
    type-checking the passed decorated callable.

    This high-level function implements this decorator's core type-checking,
    converting all unignorable PEP-compliant type hints annotating this
    callable into pure-Python code type-checking the corresponding parameters
    and return values of each call to this callable.

    Parameters
    ----------
    data : BeartypeData
        Decorated callable to be type-checked.

    Returns
    ----------
    str
        Generated function wrapper code. Specifically, either:

        * If the decorated callable requires *no* type-checking (e.g., due to
          all type hints annotating this callable being ignorable), the empty
          string. Note this edge case is distinct from a related edge case at
          the head of the :func:`beartype.beartype` decorator reducing to a
          noop for unannotated callables. By compare, this boolean is ``True``
          only for callables annotated with **ignorable type hints** (i.e.,
          :class:`object`, :class:`beartype.cave.AnyType`,
          :class:`typing.Any`): e.g.,

          .. code-block:: python

              >>> from beartype.cave import AnyType
              >>> from typing import Any
              >>> def muh_func(muh_param1: AnyType, muh_param2: object) -> Any: pass
              >>> muh_func is beartype(muh_func)
              True

        * Else, a code snippet defining the wrapper function type-checking the
          decorated callable, including (in order):

          * A signature declaring this wrapper, accepting both
            beartype-agnostic and -specific parameters. The latter include:

            * A private ``__beartype_func`` parameter initialized to the
              decorated callable. In theory, this callable should be accessible
              as a closure-style local in this wrapper. For unknown reasons
              (presumably, a subtle bug in the exec() builtin), this is *not*
              the case. Instead, a closure-style local must be simulated by
              passing this callable at function definition time as the default
              value of an arbitrary parameter. To ensure this default is *not*
              overwritten by a function accepting a parameter of the same name,
              this unlikely edge case is guarded against elsewhere.

          * Statements type checking parameters passed to the decorated
            callable.
          * A call to the decorated callable.
          * A statement type checking the value returned by the decorated
            callable.

    Raises
    ----------
    BeartypeDecorParamNameException
        If the name of any parameter declared on this callable is prefixed by
        the reserved substring ``__bear``.
    BeartypeDecorHintNonpepException
        If any type hint annotating any parameter of this callable is neither:

        * **PEP-compliant** (i.e., :mod:`beartype`-agnostic hint compliant with
          annotation-centric PEPs).
        * **PEP-noncompliant** (i.e., :mod:`beartype`-specific type hint *not*
          compliant with annotation-centric PEPs)).
    _BeartypeUtilMappingException
        If generated code type-checking any pair of parameters and returns
        erroneously declares an optional private beartype-specific parameter of
        the same name with differing default value. Since this should *never*
        happen, a private non-human-readable exception is raised in this case.
    '''
    assert data.__class__ is BeartypeData, f'{repr(data)} not @beartype data.'

    # Python code snippet type-checking all callable parameters if one or more
    # such parameters are annotated with unignorable type hints *OR* the empty
    # string otherwise.
    code_check_params = _code_check_params(data)

    # Python code snippet type-checking the callable return if this return is
    # annotated with an unignorable type hint *OR* the empty string otherwise.
    code_check_return = _code_check_return(data)

    # If the callable return requires *NO* type-checking...
    #
    # Note that this branch *CANNOT* be embedded in the prior call to the
    # _code_check_return() function, as doing so would prevent us from
    # efficiently reducing to a noop here.
    if not code_check_return:
        # If all callable parameters also require *NO* type-checking, this
        # callable itself requires *NO* type-checking. In this case, return the
        # empty string instructing the parent @beartype decorator to reduce to
        # a noop (i.e., the identity decorator returning this callable as is).
        if not code_check_params:
            return ''
        # Else, one or more callable parameters require type-checking.

        # Python code snippet calling this callable unchecked, returning the
        # value returned by this callable from this wrapper.
        code_check_return = CODE_RETURN_UNCHECKED_format(
            func_call_prefix=data.func_wrapper_code_call_prefix)
    # Else, the callable return requires type-checking.

    # Return Python code defining the wrapper type-checking this callable.
    # While there exist numerous alternatives to string formatting (e.g.,
    # appending to a list or bytearray before joining the items of that
    # iterable into a string), these alternatives are either:
    # * Slower, as in the case of a list (e.g., due to the high up-front cost
    #   of list construction).
    # * Cumbersome, as in the case of a bytearray.
    #
    # Since string concatenation is heavily optimized by the official CPython
    # interpreter, the simplest approach is the most ideal. KISS, bro.
    return (
        f'{_make_func_wrapper_signature(data)}'
        f'{code_check_params}'
        f'{code_check_return}'
    )

# ....................{ PRIVATE ~ params                  }....................
def _code_check_params(data: BeartypeData) -> str:
    '''
    Generate a Python code snippet type-checking all annotated parameters of
    the decorated callable if any *or* the empty string otherwise (i.e., if
    these parameters are unannotated).

    Parameters
    ----------
    data : BeartypeData
        Decorated callable to be type-checked.

    Returns
    ----------
    str
        Code type-checking all annotated parameters of the decorated callable.

    Raises
    ----------
    BeartypeDecorParamNameException
        If the name of any parameter declared on this callable is prefixed by
        the reserved substring ``__bear``.
    BeartypeDecorHintNonpepException
        If any type hint annotating any parameter of this callable is neither:

        * A PEP-noncompliant type hint.
        * A supported PEP-compliant type hint.
    '''
    assert data.__class__ is BeartypeData, f'{repr(data)} not @beartype data.'

    # ..................{ LOCALS ~ func                     }..................
    # Callable currently being decorated by the @beartype decorator.
    func = data.func

    # Dictionary mapping from the name of each annotated parameter accepted by
    # that callable to the type hint annotating that parameter. By prior
    # validation, this dictionary is guaranteed to exist *AND* be non-empty.
    func_arg_name_to_hint = func.__annotations__

    #FIXME: Unit test this up, please. Specifically, unit test:
    #* A callable annotated with only a single return type hint accepting both:
    #  * *NO* parameters.
    #  * One or more parameters each of which is unannotated.
    #
    #We probably already do this, but let's be double-sure here. Safety first!

    # If both...
    #
    # Note that this is purely an optimization short-circuit mildly improving
    # efficiency for the common case of callables accepting either no
    # parameters *OR* one or more parameters each of which is unannotated.
    if (
        # That callable is annotated by only one type hint *AND*...
        len(func_arg_name_to_hint) == 1 and
        # That type hint annotates that callable's return rather than a
        # parameter accepted by that callable...
        'return' in func_arg_name_to_hint
    ):
        # Then *NO* callable parameters are annotated. In this case, silently
        # reduce to a noop.
        return ''
    # Else, one or more callable parameters are annotated.

    # dict.get() method bound to the dictionary declared above, localized as a
    # negligible microoptimization. (Look. It's not *OUR* fault. Blame Guido.)
    func_arg_name_to_hint_get = func_arg_name_to_hint.get

    # Python code snippet to be returned.
    func_wrapper_code = ''

    # Python code snippet type-checking the current parameter.
    func_wrapper_code_arg = ''

    # ..................{ LOCALS ~ param                    }..................
    # Name and kind of the current parameter.
    arg_name = None
    arg_kind = None

    # True only if this callable possibly accepts one or more positional
    # parameters.
    is_args_positional = False

    # ..................{ LOCALS ~ other                    }..................
    # Human-readable label describing the current parameter.
    exception_prefix = None

    # Type hint annotating this parameter if any *OR* "_PARAM_HINT_EMPTY"
    # otherwise (i.e., if this parameter is unannotated).
    hint = None

    # ..................{ GENERATE                          }..................
    # For the name of each parameter accepted by this callable and the
    # "ParameterMeta" object describing this parameter (in declaration
    # order)...

    #FIXME: Locally remove the "arg_index" local variable (and thus avoid
    #calling the enumerate() builtin here) AFTER* refactoring @beartype to
    #generate callable-specific wrapper signatures.

    for arg_index, arg in enumerate(iter_func_args(func)):
        # Type hint annotating this parameter if any *OR* the sentinel
        # placeholder otherwise (i.e., if this parameter is unannotated).
        #
        # Note that "None" is a semantically meaningful PEP 484-compliant type
        # hint equivalent to "type(None)". Ergo, we *MUST* explicitly
        # distinguish between that type hint and unannotated parameters.
        hint = func_arg_name_to_hint_get(arg.name, SENTINEL)

        # If this parameter is unannotated, continue to the next parameter.
        if hint is SENTINEL:
            continue
        # Else, this parameter is annotated.

        # Name and kind of this parameter, localized for efficiency.
        arg_name = arg.name
        arg_kind = arg.kind

        # Human-readable labels describing the current parameter and type
        # hint annotating this parameter.
        exception_prefix = prefix_callable_decorated_param(func, arg_name)

        # If this parameter's name is reserved for use by the @beartype
        # decorator, raise an exception.
        if arg_name.startswith('__bear'):
            raise BeartypeDecorParamNameException(
                f'{exception_prefix}reserved by @beartype.')
        # If either the type of this parameter is silently ignorable, continue
        # to the next parameter.
        elif arg_kind in _PARAM_KINDS_IGNORABLE:
            continue
        # Else, this parameter is non-ignorable.

        # PEP-compliant type hint converted from this PEP-noncompliant type
        # hint if this hint is PEP-noncompliant, this hint as is if this hint
        # is both PEP-compliant and supported, *OR* raise an exception
        # otherwise (i.e., if this hint is neither PEP-noncompliant nor a
        # supported PEP-compliant hint).
        #
        # Do this first *BEFORE* passing this hint to any further callables.
        hint = sanify_hint_root(
            hint=hint,
            func=func,
            pith_name=arg_name,
            exception_prefix=f'{exception_prefix}type hint ',
        )

        # If this hint is ignorable, continue to the next parameter.
        #
        # Note that this is intentionally tested *AFTER* this hint has been
        # coerced into a PEP-compliant type hint to implicitly ignore
        # PEP-noncompliant type hints as well (e.g., "(object, int, str)").
        if is_hint_ignorable(hint):
            # print(f'Ignoring {data.func_name} parameter {arg_name} hint {repr(hint)}...')
            continue
        # Else, this hint is unignorable.
        #
        # If this unignorable parameter either may *OR* must be passed
        # positionally, record this fact. Note this conditional branch must be
        # tested after validating this parameter to be unignorable; if this
        # branch were instead nested *BEFORE* validating this parameter to be
        # unignorable, @beartype would fail to reduce to a noop for otherwise
        # ignorable callables -- which would be rather bad, really.
        elif arg_kind is ParameterKind.POSITIONAL_OR_KEYWORD:
            is_args_positional = True

        # Python code snippet type-checking this parameter against this hint.
        func_wrapper_code_arg = pep_code_check_param(
            data=data,
            hint=hint,
            arg=arg,
            arg_index=arg_index,
        )

        # Append code type-checking this parameter against this hint.
        func_wrapper_code += func_wrapper_code_arg

    # If this callable accepts one or more positional type-checked parameters,
    # prefix this code by a snippet localizing the number of these parameters.
    if is_args_positional:
        func_wrapper_code = f'{CODE_INIT_ARGS_LEN}{func_wrapper_code}'
    # Else, this callable accepts *NO* positional type-checked parameters. In
    # this case, preserve this code as is.

    # Return this code.
    return func_wrapper_code

# ....................{ PRIVATE ~ return                  }....................
def _code_check_return(data: BeartypeData) -> str:
    '''
    Generate a Python code snippet type-checking the annotated return declared
    by the decorated callable if any *or* the empty string otherwise (i.e., if
    this return is unannotated).

    Parameters
    ----------
    data : BeartypeData
        Decorated callable to be type-checked.

    Returns
    ----------
    str
        Code type-checking any annotated return of the decorated callable.

    Raises
    ----------
    :exc:`BeartypeDecorHintPep484585Exception`
        If this callable is either:

        * A coroutine *not* annotated by a :attr:`typing.Coroutine` type hint.
        * A generator *not* annotated by a :attr:`typing.Generator` type hint.
        * An asynchronous generator *not* annotated by a
          :attr:`typing.AsyncGenerator` type hint.
    :exc:`BeartypeDecorHintNonpepException`
        If the type hint annotating this return (if any) of this callable is
        neither:

        * **PEP-compliant** (i.e., :mod:`beartype`-agnostic hint compliant with
          annotation-centric PEPs).
        * **PEP-noncompliant** (i.e., :mod:`beartype`-specific type hint *not*
          compliant with annotation-centric PEPs)).
    '''
    assert data.__class__ is BeartypeData, f'{repr(data)} not @beartype data.'

    # Decorated callable.
    func = data.func

    # Type hint annotating this callable's return if any *OR* "SENTINEL"
    # otherwise (i.e., if this return is unannotated).
    #
    # Note that "None" is a semantically meaningful PEP 484-compliant type hint
    # equivalent to "type(None)". Ergo, we *MUST* explicitly distinguish
    # between that type hint and an unannotated return.
    hint = func.__annotations__.get('return', SENTINEL)

    # If this return is unannotated, silently reduce to a noop.
    if hint is SENTINEL:
        return ''
    # Else, this return is annotated.

    # This hint reduced to a simpler hint if this hint is either PEP 484- *OR*
    # 585-compliant *AND* requires reduction (e.g., from "Coroutine[None, None,
    # str]" to just "str"), raising an exception if this hint is contextually
    # invalid for this callable (e.g., generator whose return is *NOT*
    # annotated as "Generator[...]").
    #
    # Perform this reduction *BEFORE* performing subsequent tests (e.g., to
    # accept "Coroutine[None, None, typing.NoReturn]" as expected).
    hint = reduce_hint_pep484585_func_return(func)

    # Python code snippet to be returned, defaulting to the empty string
    # implying this callable's return to either be unannotated *OR* annotated
    # by a safely ignorable type hint.
    func_wrapper_code = ''

    # If this is the PEP 484-compliant "typing.NoReturn" type hint permitted
    # *ONLY* as a return annotation...
    if hint is NoReturn:
        # Default this snippet to a pre-generated snippet validating this
        # callable to *NEVER* successfully return. Yup!
        func_wrapper_code = PEP484_CODE_CHECK_NORETURN.format(
            func_call_prefix=data.func_wrapper_code_call_prefix)
    # Else, this is *NOT* "typing.NoReturn". In this case...
    else:
        # PEP-compliant type hint converted from this PEP-noncompliant type
        # hint if this hint is PEP-noncompliant, this hint as is if this hint
        # is both PEP-compliant and supported, *OR* raise an exception
        # otherwise (i.e., if this hint is neither PEP-noncompliant nor a
        # supported PEP-compliant hint).
        hint = sanify_hint_root(
            hint=hint,
            func=func,
            pith_name='return',
            exception_prefix=(
                f'{prefix_callable_decorated_return(func)}type hint '),
        )

        # If this PEP-compliant hint is unignorable, generate and return a
        # snippet type-checking this return against this hint.
        if not is_hint_ignorable(hint):
            func_wrapper_code = pep_code_check_return(data=data, hint=hint)
        # Else, this PEP-compliant hint is ignorable.
        # if not func_wrapper_code: print(f'Ignoring {data.func_name} return hint {repr(hint)}...')

    # Return this code.
    return func_wrapper_code

# ....................{ PRIVATE ~ return                  }....................
def _make_func_wrapper_signature(
    data: BeartypeData,

    # "beartype._decor._code.codesnip" string globals required only for their
    # bound "str.format" methods.
    CODE_SIGNATURE_format: Callable = CODE_SIGNATURE.format,
) -> str:
    '''
    Create and return the **signature** (i.e., callable declaration prefixing
    the body of that callable) of the decorated callable.

    Parameters
    ----------
    data : BeartypeData
        Decorated callable to be inspected.

    Yields
    ----------
    str
        Signature of this callable.
    '''
    assert data.__class__ is BeartypeData, f'{repr(data)} not @beartype data.'

    # Python code snippet declaring all optional private beartype-specific
    # parameters directly derived from the local scope established by the above
    # calls to the _code_check_params() and _code_check_return() functions.
    code_signature_params = ''.join(
        # For the name of each such parameter, compose the declaration of
        # this parameter in the signature of this wrapper from...
        (
            # Indentation prefixing all wrapper parameters.
            f'{CODE_INDENT_1}'
            # Default this parameter to the current value of the module-scoped
            # attribute of the same name, passed to the make_func() function by
            # the parent @beartype decorator. While awkward, this is the
            # optimally efficient means of exposing arbitrary attributes to the
            # body of this wrapper function.
            f'{param_name}={param_name}, '
            # For debuggability, additionally suffix this parameter by a
            # comment embedding the machine-readable representation of this
            # value, stripped of newline and truncated to a reasonable length.
            f'# is {represent_object(param_value)}\n'
        )
        for param_name, param_value in data.func_wrapper_locals.items()
    )

    # Python code snippet declaring the signature of this wrapper.
    code_signature = CODE_SIGNATURE_format(
        func_wrapper_prefix=data.func_wrapper_code_signature_prefix,
        func_wrapper_name=data.func_wrapper_name,
        func_wrapper_params=code_signature_params,
    )

    # Python code snippet of preliminary statements (e.g., local variable
    # assignments) if any *AFTER* generating snippets type-checking parameters
    # and return values, both of which modify instance variables of the
    # dataclass tested below.
    code_body_init = (
        # If the body of this wrapper requires a pseudo-random integer, append
        # code generating and localizing such an integer to this signature.
        CODE_INIT_RANDOM_INT
        if ARG_NAME_GETRANDBITS in data.func_wrapper_locals else
        # Else, this body requires *NO* such integer. In this case, preserve
        # this signature as is.
        ''
    )

    # Return this signature suffixed by zero or more preliminary statements.
    return (
        f'{code_signature}'
        f'{code_body_init}'
    )
