def solve(input_str: str) -> str:
    nums = [int(x) for x in input_str.split()]
    return str(sum(nums))
