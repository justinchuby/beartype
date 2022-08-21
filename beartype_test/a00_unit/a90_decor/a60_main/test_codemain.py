#!/usr/bin/env python3
# --------------------( LICENSE                           )--------------------
# Copyright (c) 2014-2022 Beartype authors.
# See "LICENSE" for further details.

'''
**Beartype decorator type hint code generation unit tests.**

This submodule unit tests the :func:`beartype.beartype` decorator with respect
to type-checking code dynamically generated by the
:mod:`beartype._decor._wrapper.wrappermain` submodule.
'''

# ....................{ IMPORTS                           }....................
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# WARNING: To raise human-readable test errors, avoid importing from
# package-specific submodules at module scope.
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
from beartype.roar import BeartypeDecorHintPep585DeprecationWarning
from beartype_test.util.mark.pytmark import ignore_warnings

# ....................{ TESTS                             }....................
# Prevent pytest from capturing and displaying all expected non-fatal
# beartype-specific warnings emitted by the @beartype decorator below. Urgh!
@ignore_warnings(BeartypeDecorHintPep585DeprecationWarning)
def test_codemain() -> None:
    '''
    Test the :func:`beartype.beartype` decorator with respect to type-checking
    code dynamically generated by the :mod:`beartype._decor._wrapper.wrappermain`
    submodule.

    This unit test effectively acts as a functional test and is thus the core
    test exercising decorator functionality from the end user perspective --
    the only perspective that matters in the end. Unsurprisingly, this test is
    mildly more involved than most. *Whatevah.*

    This test additionally attempts to avoid similar issues to a `prior issue
    <issue #5_>`__ of this decorator induced by repeated
    :func:`beartype.beartype` decorations of different callables annotated by
    one or more of the same PEP-compliant type hints.

    .. _issue #5:
       https://github.com/beartype/beartype/issues/5
    '''

    # Defer heavyweight imports.
    from beartype import beartype
    from beartype.roar import (
        BeartypeCallHintViolation,
        # BeartypeDecorHintPep585DeprecationWarning,
    )
    from beartype_test.a00_unit.data.hint.util.data_hintmetacls import (
        HintPithUnsatisfiedMetadata)
    from beartype_test.a00_unit.data.hint.util.data_hintmetautil import iter_hints_piths_meta
    from beartype_test.util.pytroar import raises_uncached
    from re import search

    # For each predefined type hint and associated metadata...
    for hint_pith_meta in iter_hints_piths_meta():
        # Type hint to be type-checked.
        hint = hint_pith_meta.hint_meta.hint

        # Object to type-check against this type hint.
        pith = hint_pith_meta.pith

        # Metadata describing this pith.
        pith_meta = hint_pith_meta.pith_meta
        # print(f'Type-checking PEP type hint {repr(hint_meta.hint)}...')

        # Undecorated callable both accepting a single parameter and returning
        # a value annotated by this hint whose implementation trivially reduces
        # to the identity function.
        def func_untyped(hint_param: hint) -> hint:
            return hint_param

        #FIXME: For unknown and probably uninteresting reasons, the
        #pytest.warns() context manager appears to be broken on our
        #local machine. We have no recourse but to unconditionally
        #ignore this warning at the module level. So much rage!
        #FIXME: It's likely this has something to do with the fact that
        #Python filters deprecation warnings by default. This is almost
        #certainly a pytest issue. Since this has become fairly
        #unctuous, we should probably submit a pytest issue report.
        #FIXME: Actually, pytest now appears to have explicit support for
        #testing that a code block emits a deprecation warning:
        #    with pytest.deprecated_call():
        #        myfunction(17)
        #See also: https://docs.pytest.org/en/6.2.x/warnings.html#ensuring-code-triggers-a-deprecation-warning

        # # Decorated callable declared below.
        # func_typed = None
        #
        # # If this is a deprecated PEP-compliant type hint, declare this
        # # decorated callable under a context manager asserting this
        # # declaration to emit non-fatal deprecation warnings.
        # if (
        #     isinstance(hint_meta, HintPepMetadata) and
        #     hint_meta.pep_sign in HINT_PEP_ATTRS_DEPRECATED
        # ):
        #     with pytest.warns(BeartypeDecorHintPep585DeprecationWarning):
        #         func_typed = beartype(func_untyped)
        # # Else, this is *NOT* a deprecated PEP-compliant type hint. In this
        # # case, declare this decorated callable as is.
        # else:
        #     func_typed = beartype(func_untyped)

        # @beartype-generated wrapper function type-checking this callable.
        func_typed = beartype(func_untyped)

        # If this pith violates this hint...
        if isinstance(pith_meta, HintPithUnsatisfiedMetadata):
            # Assert that iterables of uncompiled regular expression expected
            # to match and *NOT* match this message are *NOT* strings, as
            # commonly occurs when accidentally omitting a trailing comma in
            # tuples containing only one string: e.g.,
            # * "('This is a tuple, yo.',)" is a 1-tuple containing one string.
            # * "('This is a string, bro.')" is a string *NOT* contained in a
            #   1-tuple.
            assert not isinstance(
                pith_meta.exception_str_match_regexes, str)
            assert not isinstance(
                pith_meta.exception_str_not_match_regexes, str)

            # Assert this wrapper function raises the expected exception when
            # type-checking this pith against this hint.
            with raises_uncached(BeartypeCallHintViolation) as exception_info:
                func_typed(pith)

            # Exception message raised by this wrapper function.
            exception_str = str(exception_info.value)
            # print('exception message: {}'.format(exception_str))

            # Exception type localized for debuggability. Sadly, the
            # pytest.ExceptionInfo.__repr__() dunder method fails to usefully
            # describe its exception metadata.
            exception_type = exception_info.type

            # Assert this exception metadata describes the expected exception
            # as a sanity check against upstream pytest issues and/or issues
            # with our raises_uncached() context manager.
            assert issubclass(
                exception_type, BeartypeCallHintViolation)

            # Assert this exception to be public rather than private. The
            # @beartype decorator should *NEVER* raise a private exception.
            assert exception_type.__name__[0] != '_'

            # For each uncompiled regular expression expected to match this
            # message, assert this expression actually does so.
            #
            # Note that the re.search() rather than re.match() function is
            # called. The latter is rooted at the start of the string and thus
            # *ONLY* matches prefixes, while the former is *NOT* rooted at any
            # string position and thus matches arbitrary substrings as desired.
            for exception_str_match_regex in (
                pith_meta.exception_str_match_regexes):
                assert search(
                    exception_str_match_regex,
                    exception_str,
                ) is not None

            # For each uncompiled regular expression expected to *NOT* match
            # this message, assert this expression actually does so.
            for exception_str_not_match_regex in (
                pith_meta.exception_str_not_match_regexes):
                assert search(
                    exception_str_not_match_regex,
                    exception_str,
                ) is None
        # Else, this pith satisfies this hint. In this case...
        else:
            # Assert this wrapper function successfully type-checks this pith
            # against this hint *WITHOUT* modifying this pith.
            assert func_typed(pith) is pith
