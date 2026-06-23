"""Quick smoke test for the database module."""
import asyncio
from database import Database

async def test():
    db = Database(":memory:")
    await db.connect()

    # Add an account with 2 channels
    aid = await db.add_account("test_token_123", "TestAccount", ["111", "222"])
    print(f"Added account id={aid}")

    # List accounts
    accs = await db.get_all_accounts()
    print(f"Accounts: {len(accs)}")
    print(f"  Name: {accs[0]['name']}, Channels: {accs[0]['channel_ids']}")

    # List channels
    channels = await db.get_all_channels()
    print(f"Channels: {len(channels)}")

    # Get stats
    stats = await db.get_stats()
    print(f"Stats: {stats}")

    # Test eligible accounts
    eligible = await db.get_eligible_accounts("111")
    print(f"Eligible for ch 111: {len(eligible)}")

    # Record a bump
    await db.record_bump("111", aid, True)
    await db.update_channel_bump("111", 1000.0)
    await db.update_account_last_bump(aid, 1000.0)

    logs = await db.get_bump_logs(10)
    print(f"Logs: {len(logs)}, success={logs[0]['success']}")

    # Toggle disable
    await db.toggle_account(aid, False)
    acc = await db.get_account(aid)
    print(f"Enabled after toggle: {acc['enabled']}")

    await db.close()
    print("\nALL TESTS PASSED")

asyncio.run(test())
