from engine import executeScript

#script = """
#price = Fetch{OneMinuteGoldPrices}{}
#fast = ExponentialMovingAverage{0.3}{price}
#slow = SimpleMovingAverage{20}{price}
#entry = CrossAbove{}{fast, slow}
#exit = CrossAbove{}{slow, fast}
#result = PortfolioSimulation{10000}{entry, exit, price}
#"""

#memory = executeScript(script)

#print(memory.keys())
#print(memory["result"][:10])
from storage import init_db
from storage import load_result
init_db() # ensure the database and table are created before loading results
data = load_result("your-script-id-here", ["price", "result"])

print(data)
