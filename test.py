from decimal import Decimal, ROUND_DOWN

number = Decimal(0.04)
result = float(number.quantize(Decimal('0.01'), rounding=ROUND_DOWN))
print(result, type(result))
