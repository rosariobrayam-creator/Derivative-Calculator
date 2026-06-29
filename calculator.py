def ConstantRule(expr):
    return expr*0
def PowerRule(base, exponent):
    return base*exponent**(base-1)
def ProductRule(left, right):
    return APrime(left)*right + left*BPrime(right)
def QuotientRule(numerator, denominator):
    return ((denominator*APrime(numerator)) - numerator*BPrime(denominator)) / (denominator**2)
def ChainRule(outer, inner):
    return APrime(inner)

def add(left, right): return left + right
def subtract(left, right): return left - right
def multiply(left, right): return left * right
def divide(left, right):
    if right == 0:
        raise ValueError("Cannot divide by zero")
    return left / right

def APrime(expr):
    if '(' in expr and ')' in expr:
        derivativeFirstSplit = expr.split('(')
        derivativeParts = derivativeFirstSplit[1].split(')')
        if derivativeFirstSplit[0] == '':
            outer = derivativeParts[1]
        else:
            outer = derivativeFirstSplit[0]
        inner = derivativeParts[0]
        return ChainRule(outer, inner)
    elif '**' in expr:
        derivativeParts = expr.split('**')
        base = float(derivativeParts[0])
        exponent = float(derivativeParts[1])
        return PowerRule(base, exponent)
    elif '*' in expr:
        derivativeParts = expr.split('*')
        left = derivativeParts[0]
        right = derivativeParts[1]
        return ProductRule(left, right)
    elif '/' in expr:
        derivativeParts = expr.split('/')
        numerator = derivativeParts[0]
        denominator = derivativeParts[1]
        return QuotientRule(numerator, denominator)
    else:
        return ConstantRule(expr)

def BPrime(expr):
    if '(' in expr and ')' in expr:
        derivativeFirstSplit = expr.split('(')
        derivativeParts = derivativeFirstSplit[1].split(')')
        if derivativeFirstSplit[0] == '':
            outer = derivativeParts[1]
        else:
            outer = derivativeFirstSplit[0]
        inner = derivativeParts[0]
        return ChainRule(outer, inner)
    elif '**' in expr:
        derivativeParts = expr.split('**')
        base = float(derivativeParts[0])
        exponent = float(derivativeParts[1])
        return PowerRule(base, exponent)
    elif '*' in expr:
        derivativeParts = expr.split('*')
        left = derivativeParts[0]
        right = derivativeParts[1]
        return ProductRule(left, right)
    elif '/' in expr:
        derivativeParts = expr.split('/')
        numerator = derivativeParts[0]
        denominator = derivativeParts[1]
        return QuotientRule(numerator, denominator)
    else:
        return ConstantRule(expr)

operations = {
    '+': add,
    '-': subtract,
    '*': multiply,
    '/': divide,
}

print("Simple Calculator (type 'q' to quit)")
while True:
    expr = input("\nEnter expression (e.g. 3 + 5): ").strip()
    if expr.lower() == 'q':
        break
    parts = expr.split()
    if parts[0] == 'd/dx':
        if len(parts) == 2:
            print('=', APrime(parts[1]))
        else:
            print("Invalid input. Use format: d/dx <expression>")
        continue
    if len(parts) == 1:
        print('=', parts[0])
        continue
    if len(parts) != 3 or parts[1] not in operations:
        print("Invalid input. Use format: number operator number (e.g. 3 + 5)")
        continue
    try:
        left, op, right = float(parts[0]), parts[1], float(parts[2])
        result = operations[op](left, right)
        print(f"= {result:g}")
    except ValueError as e:
        print(f"Error: {e}")
