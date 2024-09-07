from decimal import Decimal, ROUND_DOWN

number = Decimal(f'{0.13*1.5}')
result = float(number.quantize(Decimal('0.01'), rounding=ROUND_DOWN))
print(result, type(result))
