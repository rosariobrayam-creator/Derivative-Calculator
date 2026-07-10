import re

LETTER_VARIABLES = set('abcdefghijklmnopqrstuvwxyz')

# ---------------------------------------------------------------------------
# Expression tree
# ---------------------------------------------------------------------------
class Const:
    def __init__(self, value):
        self.value = value

class Var:
    def __init__(self, name):
        self.name = name

class Neg:
    def __init__(self, operand):
        self.operand = operand

class BinOp:
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------
TOKEN_RE = re.compile(r'\s*(\*\*|[()+\-*/]|\d+\.\d+|\d+|[a-zA-Z])')

def tokenize(expr):
    tokens = []
    pos = 0
    while pos < len(expr):
        match = TOKEN_RE.match(expr, pos)
        if not match:
            if expr[pos].isspace():
                pos += 1
                continue
            raise ValueError(f"Unexpected character: {expr[pos]!r}")
        tokens.append(match.group(1))
        pos = match.end()
    return tokens

# ---------------------------------------------------------------------------
# Recursive-descent parser
#   expr  := term (('+' | '-') term)*
#   term  := unary (('*' | '/') unary)*
#   unary := '-' unary | power
#   power := atom ('**' unary)?         (right-associative)
#   atom  := NUMBER | VARIABLE | '(' expr ')'
# ---------------------------------------------------------------------------
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def expect(self, tok):
        if self.peek() != tok:
            raise ValueError(f"Expected {tok!r}, got {self.peek()!r}")
        return self.advance()

    def parse(self):
        node = self.parse_expr()
        if self.pos != len(self.tokens):
            raise ValueError(f"Unexpected trailing token: {self.peek()!r}")
        return node

    def parse_expr(self):
        node = self.parse_term()
        while self.peek() in ('+', '-'):
            op = self.advance()
            node = BinOp(op, node, self.parse_term())
        return node

    def parse_term(self):
        node = self.parse_unary()
        while self.peek() in ('*', '/'):
            op = self.advance()
            node = BinOp(op, node, self.parse_unary())
        return node

    def parse_unary(self):
        if self.peek() == '-':
            self.advance()
            return Neg(self.parse_unary())
        return self.parse_power()

    def parse_power(self):
        node = self.parse_atom()
        if self.peek() == '**':
            self.advance()
            exponent = self.parse_unary()
            node = BinOp('**', node, exponent)
        return node

    def parse_atom(self):
        tok = self.peek()
        if tok is None:
            raise ValueError("Unexpected end of expression")
        if tok == '(':
            self.advance()
            node = self.parse_expr()
            self.expect(')')
            return node
        self.advance()
        if re.fullmatch(r'\d+\.\d+|\d+', tok):
            return Const(float(tok) if '.' in tok else int(tok))
        if tok in LETTER_VARIABLES:
            return Var(tok)
        raise ValueError(f"Unexpected token: {tok!r}")

def parse(expr):
    return Parser(tokenize(expr)).parse()

# ---------------------------------------------------------------------------
# Differentiation (operates on the tree, not on strings)
# ---------------------------------------------------------------------------
def differentiate(node, var):
    if isinstance(node, Const):
        return Const(0)
    if isinstance(node, Var):
        return Const(1) if node.name == var else Const(0)
    if isinstance(node, Neg):
        return Neg(differentiate(node.operand, var))
    if isinstance(node, BinOp):
        if node.op in ('+', '-'):
            return BinOp(node.op, differentiate(node.left, var), differentiate(node.right, var))
        if node.op == '*':
            # Product Rule: (fg)' = f'g + fg'
            return BinOp('+',
                         BinOp('*', differentiate(node.left, var), node.right),
                         BinOp('*', node.left, differentiate(node.right, var)))
        if node.op == '/':
            # Quotient Rule: (f/g)' = (f'g - fg') / g**2
            f, g = node.left, node.right
            numerator = BinOp('-',
                              BinOp('*', differentiate(f, var), g),
                              BinOp('*', f, differentiate(g, var)))
            denominator = BinOp('**', g, Const(2))
            return BinOp('/', numerator, denominator)
        if node.op == '**':
            base, exponent = node.left, node.right
            if not isinstance(exponent, Const):
                raise NotImplementedError("Only constant exponents are supported")
            # Power Rule + Chain Rule: (u**n)' = n * u**(n-1) * u'
            power_term = BinOp('**', base, Const(exponent.value - 1))
            coefficient = BinOp('*', exponent, power_term)
            return BinOp('*', coefficient, differentiate(base, var))
    raise TypeError(f"Unhandled node: {node!r}")

# ---------------------------------------------------------------------------
# Simplification (constant folding + identities, so output stays readable)
# ---------------------------------------------------------------------------
def flatten_mul(node):
    """Break a chain of '*' nodes into a flat list of factors, e.g.
    BinOp('*', 3, BinOp('*', 4, x)) -> [Const(3), Const(4), Var('x')]."""
    if isinstance(node, BinOp) and node.op == '*':
        return flatten_mul(node.left) + flatten_mul(node.right)
    return [node]

def build_mul(factors):
    """Inverse of flatten_mul: rebuild a left-associated '*' chain from a list."""
    node = factors[0]
    for factor in factors[1:]:
        node = BinOp('*', node, factor)
    return node

def factor_base_and_exponent(node):
    """View a multiplicative factor as base**exponent, e.g. x -> (x, 1),
    x**3 -> (x, 3). Only constant exponents are unpacked; anything else
    (including x**y) is treated as an opaque factor of exponent 1 so it
    doesn't get merged with unrelated bases."""
    if isinstance(node, BinOp) and node.op == '**' and isinstance(node.right, Const):
        return node.left, node.right.value
    return node, 1

def flatten_add(node, sign=1):
    """Break a chain of '+'/'-'/unary '-' into a flat list of (sign, term)
    pairs, e.g. a-b+c -> [(1, a), (-1, b), (1, c)]."""
    if isinstance(node, BinOp) and node.op == '+':
        return flatten_add(node.left, sign) + flatten_add(node.right, sign)
    if isinstance(node, BinOp) and node.op == '-':
        return flatten_add(node.left, sign) + flatten_add(node.right, -sign)
    if isinstance(node, Neg):
        return flatten_add(node.operand, -sign)
    return [(sign, node)]

def term_coefficient_and_rest(node):
    """View an addition term as coefficient*rest, e.g. 6*x**2 -> (6, x**2),
    x -> (1, x), 5 -> (5, None). `rest=None` marks a pure number, which gets
    summed separately from the variable terms."""
    if isinstance(node, Const):
        return node.value, None
    if isinstance(node, BinOp) and node.op == '*':
        factors = flatten_mul(node)
        coefficient = 1
        rest_factors = []
        for factor in factors:
            if isinstance(factor, Const):
                coefficient *= factor.value
            else:
                rest_factors.append(factor)
        rest = build_mul(rest_factors) if rest_factors else None
        return coefficient, rest
    return 1, node

def build_signed_add(signed_terms):
    """Rebuild a '+'/'-' chain from a list of (sign, node) pairs, using '-'
    for negative terms instead of printing an ugly '+-'."""
    sign, node = signed_terms[0]
    result = node if sign == 1 else Neg(node)
    for sign, term in signed_terms[1:]:
        result = BinOp('+' if sign == 1 else '-', result, term)
    return result

def simplify(node):
    if isinstance(node, Neg):
        operand = simplify(node.operand)
        return Const(-operand.value) if isinstance(operand, Const) else Neg(operand)

    if isinstance(node, BinOp):
        left = simplify(node.left)
        right = simplify(node.right)
        op = node.op

        if isinstance(left, Const) and isinstance(right, Const):
            if op == '+': return Const(left.value + right.value)
            if op == '-': return Const(left.value - right.value)
            if op == '*': return Const(left.value * right.value)
            if op == '/': return Const(left.value / right.value)
            if op == '**': return Const(left.value ** right.value)

        if op in ('+', '-'):
            # Combine like terms across the whole +/- chain, e.g.
            # 2*x**4+3*x**4 -> 5*x**4, and fold plain numbers together too.
            terms = flatten_add(BinOp(op, left, right))
            constant_sum = 0
            combined = []      # [[rest_node, coefficient_sum], ...] in first-seen order
            index_by_key = {}  # to_string(rest) -> index into combined
            for sign, term in terms:
                coefficient, rest = term_coefficient_and_rest(term)
                signed_coefficient = sign * coefficient
                if rest is None:
                    constant_sum += signed_coefficient
                    continue
                key = to_string(rest)
                if key in index_by_key:
                    combined[index_by_key[key]][1] += signed_coefficient
                else:
                    index_by_key[key] = len(combined)
                    combined.append([rest, signed_coefficient])

            result_terms = []
            for rest, coefficient in combined:
                if coefficient == 0:
                    continue
                magnitude = abs(coefficient)
                term_sign = 1 if coefficient > 0 else -1
                term_node = rest if magnitude == 1 else BinOp('*', Const(magnitude), rest)
                result_terms.append((term_sign, term_node))

            if constant_sum != 0 or not result_terms:
                result_terms.append((1 if constant_sum >= 0 else -1, Const(abs(constant_sum))))

            return build_signed_add(result_terms)
        if op == '*':
            # Fold every constant factor in this multiplication chain into one,
            # even if the constants aren't direct siblings (e.g. 3*(4*x**3) -> 12*x**3),
            # and combine same-base powers by adding exponents (x**2*x**3 -> x**5).
            factors = flatten_mul(BinOp('*', left, right))
            const_product = 1
            grouped_bases = []       # [[base_node, exponent_sum], ...] in first-seen order
            index_by_key = {}        # to_string(base) -> index into grouped_bases
            for factor in factors:
                if isinstance(factor, Const):
                    const_product *= factor.value
                    continue
                base, exponent = factor_base_and_exponent(factor)
                key = to_string(base)
                if key in index_by_key:
                    grouped_bases[index_by_key[key]][1] += exponent
                else:
                    index_by_key[key] = len(grouped_bases)
                    grouped_bases.append([base, exponent])

            others = []
            for base, exponent in grouped_bases:
                if exponent == 0:
                    continue  # base**0 == 1, drops out of the product
                elif exponent == 1:
                    others.append(base)
                else:
                    others.append(BinOp('**', base, Const(exponent)))

            if const_product == 0:
                return Const(0)
            if not others:
                return Const(const_product)
            if const_product == 1:
                return build_mul(others)
            return build_mul([Const(const_product)] + others)
        if op == '/':
            if isinstance(left, Const) and left.value == 0: return Const(0)
            if isinstance(right, Const) and right.value == 1: return left
        if op == '**':
            if isinstance(right, Const) and right.value == 1: return left
            if isinstance(right, Const) and right.value == 0: return Const(1)

        return BinOp(op, left, right)

    return node

# ---------------------------------------------------------------------------
# Pretty-printer (precedence-aware, only adds parens when needed)
# ---------------------------------------------------------------------------
PRECEDENCE = {'+': 1, '-': 1, '*': 2, '/': 2, '**': 3}

def to_string(node, parent_prec=0):
    if isinstance(node, Const):
        value = node.value
        return str(int(value)) if float(value).is_integer() else str(value)
    if isinstance(node, Var):
        return node.name
    if isinstance(node, Neg):
        text = f'-{to_string(node.operand, 4)}'
        return f'({text})' if parent_prec > 4 else text
    if isinstance(node, BinOp):
        prec = PRECEDENCE[node.op]
        # '-', '/', '**' are not associative on the right, so force parens there
        right_prec = prec + 1 if node.op in ('-', '/', '**') else prec
        text = f'{to_string(node.left, prec)}{node.op}{to_string(node.right, right_prec)}'
        return f'({text})' if parent_prec > prec else text
    raise TypeError(f"Unhandled node: {node!r}")

# ---------------------------------------------------------------------------
# Public entry point used by the REPL
# ---------------------------------------------------------------------------
def find_variable(expr):
    used = sorted(set(c for c in expr if c.isalpha()))
    if 'x' in used:
        return 'x'
    if len(used) == 1:
        return used[0]
    if not used:
        return None
    raise ValueError(f"Ambiguous variable in expression with multiple letters: {used}")

def APrime(expr, var=None):
    tree = parse(expr)
    var = var or find_variable(expr) or 'x'
    return to_string(simplify(differentiate(tree, var)))

def add(left, right): return left + right
def subtract(left, right): return left - right
def multiply(left, right): return left * right
def divide(left, right):
    if right == 0:
        raise ValueError("Cannot divide by zero")
    return left / right

operations = {
    '+': add,
    '-': subtract,
    '*': multiply,
    '/': divide,
}

if __name__ == '__main__':
    print("Simple Calculator (type 'q' to quit)")
    while True:
        expr = input("\nEnter expression (e.g. 3 + 5): ").strip()
        if expr.lower() == 'q':
            break
        parts = expr.split()
        if parts[0] == 'd/dx':
            if len(parts) == 2:
                try:
                    print('=', APrime(parts[1]))
                except (ValueError, NotImplementedError) as e:
                    print(f"Error: {e}")
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
