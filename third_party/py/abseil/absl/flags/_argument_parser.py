# Copyright 2017 The Abseil Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Contains base classes used to parse and convert arguments.

Do NOT import this module directly. Import the flags package and use the
aliases defined at the package level instead.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import csv
import io
import string

from absl.flags import _helpers
import six


def _is_integer_type(instance):
  """Returns True if instance is an integer, and not a bool."""
  return (isinstance(instance, six.integer_types) and
          not isinstance(instance, bool))


class _ArgumentParserCache(type):
  """Metaclass used to cache and share argument parsers among flags."""

  _instances = {}

  def __call__(self, *args, **kwargs):
    """Returns an instance of the argument parser cls.

    This method overrides behavior of the __new__ methods in
    all subclasses of ArgumentParser (inclusive). If an instance
    for cls with the same set of arguments exists, this instance is
    returned, otherwise a new instance is created.

    If any keyword arguments are defined, or the values in args
    are not hashable, this method always returns a new instance of
    cls.

    Args:
      *args: Positional initializer arguments.
      **kwargs: Initializer keyword arguments.

    Returns:
      An instance of cls, shared or new.
    """
    if kwargs:
      return type.__call__(self, *args, **kwargs)
    instances = self._instances
    key = (self, ) + tuple(args)
    try:
      return instances[key]
    except KeyError:
        # No cache entry for key exists, create a new one.
      return instances.setdefault(key, type.__call__(self, *args))
    except TypeError:
        # An object in args cannot be hashed, always return
        # a new instance.
      return type.__call__(self, *args)


class ArgumentParser(six.with_metaclass(_ArgumentParserCache, object)):
  """Base class used to parse and convert arguments.

  The parse() method checks to make sure that the string argument is a
  legal value and convert it to a native type.  If the value cannot be
  converted, it should throw a 'ValueError' exception with a human
  readable explanation of why the value is illegal.

  Subclasses should also define a syntactic_help string which may be
  presented to the user to describe the form of the legal values.

  Argument parser classes must be stateless, since instances are cached
  and shared between flags. Initializer arguments are allowed, but all
  member variables must be derived from initializer arguments only.
  """

  syntactic_help = ''

  def parse(self, argument):
    """Parses the string argument and returns the native value.

    By default it returns its argument unmodified.

    Args:
      argument: string argument passed in the commandline.

    Raises:
      ValueError: Raised when it fails to parse the argument.
      TypeError: Raised when the argument has the wrong type.

    Returns:
      The parsed value in native type.
    """
    if not isinstance(argument, six.string_types):
      raise TypeError(f'flag value must be a string, found "{type(argument)}"')
    return argument

  def flag_type(self):
    """Returns a string representing the type of the flag."""
    return 'string'

  def _custom_xml_dom_elements(self, doc):
    """Returns a list of minidom.Element to add additional flag information.

    Args:
      doc: minidom.Document, the DOM document it should create nodes from.
    """
    del doc  # Unused.
    return []


class ArgumentSerializer(object):
  """Base class for generating string representations of a flag value."""

  def serialize(self, value):
    """Returns a serialized string of the value."""
    return _helpers.str_or_unicode(value)


class NumericParser(ArgumentParser):
  """Parser of numeric values.

  Parsed value may be bounded to a given upper and lower bound.
  """

  def is_outside_bounds(self, val):
    """Returns whether the value is outside the bounds or not."""
    return ((self.lower_bound is not None and val < self.lower_bound) or
            (self.upper_bound is not None and val > self.upper_bound))

  def parse(self, argument):
    """See base class."""
    val = self.convert(argument)
    if self.is_outside_bounds(val):
      raise ValueError(f'{val} is not {self.syntactic_help}')
    return val

  def _custom_xml_dom_elements(self, doc):
    elements = []
    if self.lower_bound is not None:
      elements.append(_helpers.create_xml_dom_element(
          doc, 'lower_bound', self.lower_bound))
    if self.upper_bound is not None:
      elements.append(_helpers.create_xml_dom_element(
          doc, 'upper_bound', self.upper_bound))
    return elements

  def convert(self, argument):
    """Returns the correct numeric value of argument.

    Subclass must implement this method, and raise TypeError if argument is not
    string or has the right numeric type.

    Args:
      argument: string argument passed in the commandline, or the numeric type.

    Raises:
      TypeError: Raised when argument is not a string or the right numeric type.
      ValueError: Raised when failed to convert argument to the numeric value.
    """
    raise NotImplementedError


class FloatParser(NumericParser):
  """Parser of floating point values.

  Parsed value may be bounded to a given upper and lower bound.
  """
  number_article = 'a'
  number_name = 'number'
  syntactic_help = ' '.join((number_article, number_name))

  def __init__(self, lower_bound=None, upper_bound=None):
    super(FloatParser, self).__init__()
    self.lower_bound = lower_bound
    self.upper_bound = upper_bound
    sh = self.syntactic_help
    if lower_bound is not None and upper_bound is not None:
      sh = f'{sh} in the range [{lower_bound}, {upper_bound}]'
    elif lower_bound == 0:
      sh = f'a non-negative {self.number_name}'
    elif upper_bound == 0:
      sh = f'a non-positive {self.number_name}'
    elif upper_bound is not None:
      sh = f'{self.number_name} <= {upper_bound}'
    elif lower_bound is not None:
      sh = f'{self.number_name} >= {lower_bound}'
    self.syntactic_help = sh

  def convert(self, argument):
    """Returns the float value of argument."""
    if _is_integer_type(argument) or isinstance(argument,
                                                (float, six.string_types)):
      return float(argument)
    else:
      raise TypeError(
          f'Expect argument to be a string, int, or float, found {type(argument)}'
      )

  def flag_type(self):
    """See base class."""
    return 'float'


class IntegerParser(NumericParser):
  """Parser of an integer value.

  Parsed value may be bounded to a given upper and lower bound.
  """
  number_article = 'an'
  number_name = 'integer'
  syntactic_help = ' '.join((number_article, number_name))

  def __init__(self, lower_bound=None, upper_bound=None):
    super(IntegerParser, self).__init__()
    self.lower_bound = lower_bound
    self.upper_bound = upper_bound
    sh = self.syntactic_help
    if lower_bound is not None and upper_bound is not None:
      sh = f'{sh} in the range [{lower_bound}, {upper_bound}]'
    elif lower_bound == 1:
      sh = f'a positive {self.number_name}'
    elif upper_bound == -1:
      sh = f'a negative {self.number_name}'
    elif lower_bound == 0:
      sh = f'a non-negative {self.number_name}'
    elif upper_bound == 0:
      sh = f'a non-positive {self.number_name}'
    elif upper_bound is not None:
      sh = f'{self.number_name} <= {upper_bound}'
    elif lower_bound is not None:
      sh = f'{self.number_name} >= {lower_bound}'
    self.syntactic_help = sh

  def convert(self, argument):
    """Returns the int value of argument."""
    if _is_integer_type(argument):
      return argument
    elif isinstance(argument, six.string_types):
      base = 10
      if len(argument) > 2 and argument[0] == '0':
        if argument[1] == 'o':
          base = 8
        elif argument[1] == 'x':
          base = 16
      return int(argument, base)
    else:
      raise TypeError(
          f'Expect argument to be a string or int, found {type(argument)}')

  def flag_type(self):
    """See base class."""
    return 'int'


class BooleanParser(ArgumentParser):
  """Parser of boolean values."""

  def parse(self, argument):
    """See base class."""
    if isinstance(argument, str):
      if argument.lower() in ('true', 't', '1'):
        return True
      elif argument.lower() in ('false', 'f', '0'):
        return False
    elif isinstance(argument, six.integer_types):
      # Only allow bool or integer 0, 1.
      # Note that float 1.0 == True, 0.0 == False.
      bool_value = bool(argument)
      if argument == bool_value:
        return bool_value

    raise ValueError('Non-boolean argument to boolean flag', argument)

  def flag_type(self):
    """See base class."""
    return 'bool'


class EnumParser(ArgumentParser):
  """Parser of a string enum value (a string value from a given set)."""

  def __init__(self, enum_values, case_sensitive=True):
    """Initializes EnumParser.

    Args:
      enum_values: [str], a non-empty list of string values in the enum.
      case_sensitive: bool, whether or not the enum is to be case-sensitive.

    Raises:
      ValueError: When enum_values is empty.
    """
    if not enum_values:
      raise ValueError(f'enum_values cannot be empty, found "{enum_values}"')
    super(EnumParser, self).__init__()
    self.enum_values = enum_values
    self.case_sensitive = case_sensitive

  def parse(self, argument):
    """Determines validity of argument and returns the correct element of enum.

    Args:
      argument: str, the supplied flag value.

    Returns:
      The first matching element from enum_values.

    Raises:
      ValueError: Raised when argument didn't match anything in enum.
    """
    if self.case_sensitive:
      if argument in self.enum_values:
        return argument
      else:
        raise ValueError(f"value should be one of <{'|'.join(self.enum_values)}>")
    elif argument.upper() not in [value.upper() for value in self.enum_values]:
      raise ValueError(f"value should be one of <{'|'.join(self.enum_values)}>")
    else:
      return [value for value in self.enum_values
              if value.upper() == argument.upper()][0]

  def flag_type(self):
    """See base class."""
    return 'string enum'


class ListSerializer(ArgumentSerializer):

  def __init__(self, list_sep):
    self.list_sep = list_sep

  def serialize(self, value):
    """See base class."""
    return self.list_sep.join([_helpers.str_or_unicode(x) for x in value])


class CsvListSerializer(ArgumentSerializer):

  def __init__(self, list_sep):
    self.list_sep = list_sep

  def serialize(self, value):
    """Serializes a list as a CSV string or unicode."""
    if six.PY2:
      # In Python2 csv.writer doesn't accept unicode, so we convert to UTF-8.
      output = io.BytesIO()
      csv.writer(output).writerow([unicode(x).encode('utf-8') for x in value])
      serialized_value = output.getvalue().decode('utf-8').strip()
    else:
      # In Python3 csv.writer expects a text stream.
      output = io.StringIO()
      csv.writer(output).writerow([str(x) for x in value])
      serialized_value = output.getvalue().strip()

    # We need the returned value to be pure ascii or Unicodes so that
    # when the xml help is generated they are usefully encodable.
    return _helpers.str_or_unicode(serialized_value)


class BaseListParser(ArgumentParser):
  """Base class for a parser of lists of strings.

  To extend, inherit from this class; from the subclass __init__, call

      BaseListParser.__init__(self, token, name)

  where token is a character used to tokenize, and name is a description
  of the separator.
  """

  def __init__(self, token=None, name=None):
    assert name
    super(BaseListParser, self).__init__()
    self._token = token
    self._name = name
    self.syntactic_help = f'a {self._name} separated list'

  def parse(self, argument):
    """See base class."""
    if isinstance(argument, list):
      return argument
    elif not argument:
      return []
    else:
      return [s.strip() for s in argument.split(self._token)]

  def flag_type(self):
    """See base class."""
    return f'{self._name} separated list of strings'


class ListParser(BaseListParser):
  """Parser for a comma-separated list of strings."""

  def __init__(self):
    super(ListParser, self).__init__(',', 'comma')

  def parse(self, argument):
    """Parses argument as comma-separated list of strings."""
    if isinstance(argument, list):
      return argument
    elif not argument:
      return []
    else:
      try:
        return [s.strip() for s in list(csv.reader([argument], strict=True))[0]]
      except csv.Error as e:
        # Provide a helpful report for case like
        #   --listflag="$(printf 'hello,\nworld')"
        # IOW, list flag values containing naked newlines.  This error
        # was previously "reported" by allowing csv.Error to
        # propagate.
        raise ValueError('Unable to parse the value %r as a %s: %s'
                         % (argument, self.flag_type(), e))

  def _custom_xml_dom_elements(self, doc):
    elements = super(ListParser, self)._custom_xml_dom_elements(doc)
    elements.append(_helpers.create_xml_dom_element(
        doc, 'list_separator', repr(',')))
    return elements


class WhitespaceSeparatedListParser(BaseListParser):
  """Parser for a whitespace-separated list of strings."""

  def __init__(self, comma_compat=False):
    """Initializer.

    Args:
      comma_compat: bool, whether to support comma as an additional separator.
          If False then only whitespace is supported.  This is intended only for
          backwards compatibility with flags that used to be comma-separated.
    """
    self._comma_compat = comma_compat
    name = 'whitespace or comma' if self._comma_compat else 'whitespace'
    super(WhitespaceSeparatedListParser, self).__init__(None, name)

  def parse(self, argument):
    """Parses argument as whitespace-separated list of strings.

    It also parses argument as comma-separated list of strings if requested.

    Args:
      argument: string argument passed in the commandline.

    Returns:
      [str], the parsed flag value.
    """
    if isinstance(argument, list):
      return argument
    elif not argument:
      return []
    else:
      if self._comma_compat:
        argument = argument.replace(',', ' ')
      return argument.split()

  def _custom_xml_dom_elements(self, doc):
    elements = super(WhitespaceSeparatedListParser, self
                    )._custom_xml_dom_elements(doc)
    separators = list(string.whitespace)
    if self._comma_compat:
      separators.append(',')
    separators.sort()
    for sep_char in separators:
      elements.append(_helpers.create_xml_dom_element(
          doc, 'list_separator', repr(sep_char)))
    return elements
