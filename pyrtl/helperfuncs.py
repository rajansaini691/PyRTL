""" Helper functions that make constructing hardware easier.
"""

from __future__ import print_function, unicode_literals

import numbers
import six
import math

from .core import working_block, _NameIndexer
from .pyrtlexceptions import PyrtlError, PyrtlInternalError
from .wire import WireVector, Input, Output, Const, Register

# -----------------------------------------------------------------
#        ___       __   ___  __   __
#  |__| |__  |    |__) |__  |__) /__`
#  |  | |___ |___ |    |___ |  \ .__/
#


probeIndexer = _NameIndexer('Probe-')


def probe(w, name=None):
    """ Print useful information about a WireVector when in debug mode.

    :param w: WireVector from which to get info
    :param name: optional name for probe (defaults to an autogenerated name)
    :return: original WireVector w

    Probe can be inserted into a existing design easily as it returns the
    original wire unmodified. For example ``y <<= x[0:3] + 4`` could be turned
    into ``y <<= probe(x)[0:3] + 4`` to give visibility into both the origin of
    ``x`` (including the line that WireVector was originally created) and
    the run-time values of ``x`` (which will be named and thus show up by
    default in a trace.  Likewise ``y <<= probe(x[0:3]) + 4``,
    ``y <<= probe(x[0:3] + 4)``, and ``probe(y) <<= x[0:3] + 4`` are all
    valid uses of `probe`.

    Note: `probe` does actually add a wire to the working block of w (which can
    confuse various post-processing transforms such as output to verilog).
    """
    if not isinstance(w, WireVector):
        raise PyrtlError('Only WireVectors can be probed')

    if name is None:
        name = '(%s: %s)' % (probeIndexer.make_valid_string(), w.name)
    print("Probe: " + name + ' ' + get_stack(w))

    p = Output(name=name, block=w._block, clock=w.clock)
    p <<= w  # late assigns len from w automatically
    return w


assertIndexer = _NameIndexer('assertion')


def rtl_assert(w, exp, block=None):
    """ Add hardware assertions to be checked on the RTL design.

    :param w: should be a WireVector
    :param Exception exp: Exception to throw when assertion fails
    :param Block block: block to which the assertion should be added (default to working block)
    :return: the Output wire for the assertion (can be ignored in most cases)

    If at any time during execution the wire w is not `true` (i.e. asserted low)
    then simulation will raise exp.
    """
    block = working_block(block)

    if not isinstance(w, WireVector):
        raise PyrtlError('Only WireVectors can be asserted with rtl_assert')
    if len(w) != 1:
        raise PyrtlError('rtl_assert checks only a WireVector of bitwidth 1')
    if not isinstance(exp, Exception):
        raise PyrtlError('the second argument to rtl_assert must be an instance of Exception')
    if isinstance(exp, KeyError):
        raise PyrtlError('the second argument to rtl_assert cannot be a KeyError')
    if w not in block.wirevector_set:
        raise PyrtlError('assertion wire not part of the block to which it is being added')
    if w not in block.wirevector_set:
        raise PyrtlError('assertion not a known wirevector in the target block')

    if w in block.rtl_assert_dict:
        raise PyrtlInternalError('assertion conflicts with existing registered assertion')

    name = assertIndexer.make_valid_string()
    assert_wire = Output(bitwidth=1, name=name, block=block, clock=w.clock)
    assert_wire <<= w
    block.rtl_assert_dict[assert_wire] = exp
    return assert_wire


def check_rtl_assertions(sim):
    """ Checks the values in sim to see if any registers assertions fail.

    :param sim: Simulation in which to check the assertions
    :return: None
    """

    for (w, exp) in sim.block.rtl_assert_dict.items():
        try:
            value = sim.inspect(w)
            if not value:
                raise exp
        except KeyError:
            pass


def input_list(names, bitwidth=None):
    """ Allocate and return a list of Inputs.

    :param names: Names for the Inputs. Can be a list or single comma/space-separated string
    :param bitwidth: The desired bitwidth for the resulting Inputs.
    :return: List of Inputs.

    Equivalent to: ::

        wirevector_list(names, bitwidth, wvtype=pyrtl.wire.Input)

    """
    return wirevector_list(names, bitwidth, wvtype=Input)


def output_list(names, bitwidth=None):
    """ Allocate and return a list of Outputs.

    :param names: Names for the Outputs. Can be a list or single comma/space-separated string
    :param bitwidth: The desired bitwidth for the resulting Outputs.
    :return: List of Outputs.

    Equivalent to: ::

        wirevector_list(names, bitwidth, wvtype=pyrtl.wire.Output)

    """
    return wirevector_list(names, bitwidth, wvtype=Output)


def register_list(names, bitwidth=None):
    """ Allocate and return a list of Registers.

    :param names: Names for the Registers. Can be a list or single comma/space-separated string
    :param bitwidth: The desired bitwidth for the resulting Registers.
    :return: List of Registers.

    Equivalent to: ::

        wirevector_list(names, bitwidth, wvtype=pyrtl.wire.Register)

    """
    return wirevector_list(names, bitwidth, wvtype=Register)


def wirevector_list(names, bitwidth=None, wvtype=WireVector):
    """ Allocate and return a list of WireVectors.

    :param names: Names for the WireVectors. Can be a list or single comma/space-separated string
    :param bitwidth: The desired bitwidth for the resulting WireVectors.
    :param WireVector wvtype: Which WireVector type to create.
    :return: List of WireVectors.

    Additionally, the ``names`` string can also contain an additional bitwidth specification
    separated by a ``/`` in the name. This cannot be used in combination with a ``bitwidth``
    value other than ``1``.

    Examples: ::

        wirevector_list(['name1', 'name2', 'name3'])
        wirevector_list('name1, name2, name3')
        wirevector_list('input1 input2 input3', bitwidth=8, wvtype=pyrtl.wire.Input)
        wirevector_list('output1, output2 output3', bitwidth=3, wvtype=pyrtl.wire.Output)
        wirevector_list('two_bits/2, four_bits/4, eight_bits/8')
        wirevector_list(['name1', 'name2', 'name3'], bitwidth=[2, 4, 8])

    """
    if isinstance(names, str):
        names = names.replace(',', ' ').split()

    if any('/' in name for name in names) and bitwidth is not None:
        raise PyrtlError('only one of optional "/" or bitwidth parameter allowed')

    if bitwidth is None:
        bitwidth = 1
    if isinstance(bitwidth, numbers.Integral):
        bitwidth = [bitwidth]*len(names)
    if len(bitwidth) != len(names):
        raise ValueError('number of names ' + str(len(names))
                         + ' should match number of bitwidths ' + str(len(bitwidth)))

    wirelist = []
    for fullname, bw in zip(names, bitwidth):
        try:
            name, bw = fullname.split('/')
        except ValueError:
            name, bw = fullname, bw
        wirelist.append(wvtype(bitwidth=int(bw), name=name))
    return wirelist


def val_to_signed_integer(value, bitwidth):
    """ Return value as intrepreted as a signed integer under twos complement.

    :param value: a python integer holding the value to convert
    :param bitwidth: the length of the integer in bits to assume for conversion

    Given an unsigned integer (not a wirevector!) covert that to a signed
    integer.  This is useful for printing and interpreting values which are
    negative numbers in twos complement. ::

        val_to_signed_integer(0xff, 8) == -1
    """
    if isinstance(value, WireVector) or isinstance(bitwidth, WireVector):
        raise PyrtlError('inputs must not be wirevectors')
    if bitwidth < 1:
        raise PyrtlError('bitwidth must be a positive integer')

    neg_mask = 1 << (bitwidth - 1)
    neg_part = value & neg_mask

    pos_mask = neg_mask - 1
    pos_part = value & pos_mask

    return pos_part - neg_part


def formatted_str_to_val(data, format, enum_set=None):
    """ Return an unsigned integer representation of the data given format specified.

    :param data: a string holding the value to convert
    :param format: a string holding a format which will be used to convert the data string
    :param enum_set: an iterable of enums which are used as part of the converstion process

    Given a string (not a wirevector!) covert that to an unsigned integer ready for input
    to the simulation enviornment.  This helps deal with signed/unsigned numbers (simulation
    assumes the values have been converted via two's complement already), but it also takes
    hex, binary, and enum types as inputs.  It is easiest to see how it works with some
    examples. ::

        formatted_str_to_val('2', 's3') == 2  # 0b010
        formatted_str_to_val('-1', 's3') == 7  # 0b111
        formatted_str_to_val('101', 'b3') == 5
        formatted_str_to_val('5', 'u3') == 5
        formatted_str_to_val('-3', 's3') == 5
        formatted_str_to_val('a', 'x3') == 10
        class Ctl(Enum):
            ADD = 5
            SUB = 12
        formatted_str_to_val('ADD', 'e3/Ctl', [Ctl]) == 5
        formatted_str_to_val('SUB', 'e3/Ctl', [Ctl]) == 12

    """
    type = format[0]
    bitwidth = int(format[1:].split('/')[0])
    bitmask = (1 << bitwidth)-1
    if type == 's':
        rval = int(data) & bitmask
    elif type == 'x':
        rval = int(data, 16)
    elif type == 'b':
        rval = int(data, 2)
    elif type == 'u':
        rval = int(data)
        if rval < 0:
            raise PyrtlError('unsigned format requested, but negative value provided')
    elif type == 'e':
        enumname = format.split('/')[1]
        enum_inst_list = [e for e in enum_set if e.__name__ == enumname]
        if len(enum_inst_list) == 0:
            raise PyrtlError('enum "{}" not found in passed enum_set "{}"'
                             .format(enumname, enum_set))
        rval = getattr(enum_inst_list[0], data).value
    else:
        raise PyrtlError('unknown format type {}'.format(format))
    return rval


def val_to_formatted_str(val, format, enum_set=None):
    """ Return a string representation of the value given format specified.

    :param val: a string holding an unsigned integer to convert
    :param format: a string holding a format which will be used to convert the data string
    :param enum_set: an iterable of enums which are used as part of the converstion process

    Given an unsigned integer (not a wirevector!) covert that to a strong ready for output
    to a human to interpret.  This helps deal with signed/unsigned numbers (simulation
    operates on values that have been converted via two's complement), but it also generates
    hex, binary, and enum types as outputs.  It is easiest to see how it works with some
    examples. ::

        formatted_str_to_val(2, 's3') == '2'
        formatted_str_to_val(7, 's3') == '-1'
        formatted_str_to_val(5, 'b3') == '101'
        formatted_str_to_val(5, 'u3') == '5'
        formatted_str_to_val(5, 's3') == '-3'
        formatted_str_to_val(10, 'x3') == 'a'
        class Ctl(Enum):
            ADD = 5
            SUB = 12
        formatted_str_to_val('ADD', 'e3/Ctl', [Ctl]) == 5
        formatted_str_to_val('SUB', 'e3/Ctl', [Ctl]) == 12

    """
    type = format[0]
    bitwidth = int(format[1:].split('/')[0])
    bitmask = (1 << bitwidth)-1
    if type == 's':
        rval = str(val_to_signed_integer(val, bitwidth))
    elif type == 'x':
        rval = hex(val)[2:]  # cuts off '0x' at the start
    elif type == 'b':
        rval = bin(val)[2:]  # cuts off '0b' at the start
    elif type == 'u':
        rval = str(int(val))  # nothing fancy
    elif type == 'e':
        enumname = format.split('/')[1]
        enum_inst_list = [e for e in enum_set if e.__name__ == enumname]
        if len(enum_inst_list) == 0:
            raise PyrtlError('enum "{}" not found in passed enum_set "{}"'
                             .format(enumname, enum_set))
        rval = enum_inst_list[0](val).name
    else:
        raise PyrtlError('unknown format type {}'.format(format))
    return rval


def get_stacks(*wires):
    call_stack = getattr(wires[0], 'init_call_stack', None)
    if not call_stack:
        return '    No call info found for wires: use set_debug_mode() ' \
               'to provide more information\n'
    else:
        return '\n'.join(str(wire) + ":\n" + get_stack(wire) for wire in wires)


def get_stack(wire):
    if not isinstance(wire, WireVector):
        raise PyrtlError('Only WireVectors can be traced')

    call_stack = getattr(wire, 'init_call_stack', None)
    if call_stack:
        frames = ' '.join(frame for frame in call_stack[:-1])
        return "Wire Traceback, most recent call last \n" + frames + "\n"
    else:
        return '    No call info found for wire: use set_debug_mode()'\
               ' to provide more information'


def _check_for_loop(block=None):
    block = working_block(block)
    logic_left = block.logic.copy()
    wires_left = block.wirevector_subset(exclude=(Input, Const, Output, Register))
    prev_logic_left = len(logic_left) + 1
    while prev_logic_left > len(logic_left):
        prev_logic_left = len(logic_left)
        nets_to_remove = set()  # bc it's not safe to mutate a set inside its own iterator
        for net in logic_left:
            if not any(n_wire in wires_left for n_wire in net.args):
                nets_to_remove.add(net)
                wires_left.difference_update(net.dests)
        logic_left -= nets_to_remove

    if 0 == len(logic_left):
        return None
    return wires_left, logic_left


def find_loop(block=None):
    block = working_block(block)
    block.sanity_check()  # make sure that the block is sane first

    result = _check_for_loop(block)
    if not result:
        return
    wires_left, logic_left = result
    import random

    class _FilteringState(object):
        def __init__(self, dst_w):
            self.dst_w = dst_w
            self.arg_num = -1

    def dead_end():
        # clean up after a wire is found to not be part of the loop
        wires_left.discard(cur_item.dst_w)
        current_wires.discard(cur_item.dst_w)
        del checking_stack[-1]

    # now making a map to quickly look up nets
    dest_nets = {dest_w: net_ for net_ in logic_left for dest_w in net_.dests}
    initial_w = random.sample(wires_left, 1)[0]

    current_wires = set()
    checking_stack = [_FilteringState(initial_w)]

    # we don't use a recursive method as Python has a limited stack (default: 999 frames)
    while len(checking_stack):
        cur_item = checking_stack[-1]
        if cur_item.arg_num == -1:
            #  first time testing this item
            if cur_item.dst_w not in wires_left:
                dead_end()
                continue
            current_wires.add(cur_item.dst_w)
            cur_item.net = dest_nets[cur_item.dst_w]
            if cur_item.net.op == 'r':
                dead_end()
                continue
        cur_item.arg_num += 1  # go to the next item
        if cur_item.arg_num == len(cur_item.net.args):
            dead_end()
            continue
        next_wire = cur_item.net.args[cur_item.arg_num]
        if next_wire not in current_wires:
            current_wires.add(next_wire)
            checking_stack.append(_FilteringState(next_wire))
        else:  # We have found the loop!!!!!
            loop_info = []
            for f_state in reversed(checking_stack):
                loop_info.append(f_state)
                if f_state.dst_w is next_wire:
                    break
            else:
                raise PyrtlError("Shouldn't get here! Couldn't figure out the loop")
            return loop_info
    raise PyrtlError("Error in detecting loop")


def find_and_print_loop(block=None):
    loop_data = find_loop(block)
    print_loop(loop_data)
    return loop_data


def print_loop(loop_data):
    if not loop_data:
        print("No Loop Found")
    else:
        print("Loop found:")
        print('\n'.join("{}".format(fs.net) for fs in loop_data))
        # print '\n'.join("{} (dest wire: {})".format(fs.net, fs.dst_w) for fs in loop_info)
        print("")


def _currently_in_ipython():
    """ Return true if running under ipython, otherwise return False. """
    try:
        __IPYTHON__  # pylint: disable=undefined-variable
        return True
    except NameError:
        return False


class _NetCount(object):
    """
    Helper class to track when to stop an iteration that depends on number of nets

    Mainly useful for iterations that are for optimization
    """
    def __init__(self, block=None):
        self.block = working_block(block)
        self.prev_nets = len(self.block.logic) * 1000

    def shrank(self, block=None, percent_diff=0, abs_diff=1):
        """
        Returns whether a block has less nets than before

        :param Block block: block to check (if changed)
        :param Number percent_diff: percentage difference threshold
        :param int abs_diff: absolute difference threshold
        :return: boolean

        This function checks whether the change in the number of
        nets is greater than the percentage and absolute difference
        thresholds.
        """
        if block is None:
            block = self.block
        cur_nets = len(block.logic)
        net_goal = self.prev_nets * (1 - percent_diff) - abs_diff
        less_nets = (cur_nets <= net_goal)
        self.prev_nets = cur_nets
        return less_nets

    shrinking = shrank
