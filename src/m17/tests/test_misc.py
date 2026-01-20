from m17.misc import print_4bits, print_8bits, print_16bits, print_bits


def test_b():
    """Test the binary print functions
    :param x: number to test

    """
    x = 0b1010
    print(print_4bits(int(x)))
    print(print_bits(int(x)))
    print(print_8bits(int(x)))
    print(print_16bits(int(x)))
