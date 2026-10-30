#!/usr/bin/env python3
"""Exercise the production buyer decision block with native-sized input doubles."""
import os
from pathlib import Path
import subprocess
import tempfile

project = Path(os.environ['WOW_PROJECT_ROOT']).resolve(strict=True)
subprocess.run([str(project / 'scripts/wow-build-host-guard')], check=True)
source = (Path(__file__).resolve().parents[1] / 'src/AuctionHouseBot.cpp').read_text()
start = source.index("        // Calculate a potential price for the item", source.index('void AuctionHouseBot::AddNewAuctionBuyerBotBid('))
end = source.index('        if (debug_Out)', start)
fixture = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>
using uint32 = uint32_t;
using uint64 = uint64_t;
struct Auction {
    uint32 buyout, bid, startbid;
    uint32 GetAuctionOutBid() { uint32 n = uint32(bid * 5.0f / 100.0f); return n ? n : 1; }
};
struct Item { uint32 count; uint32 GetCount() { return count; } };
struct Prototype { uint32 ItemId; };
struct Decision { bool buy, bid, prevented; uint64 amount; };
Decision decide(uint32 count, uint32 buyout, uint32 startbid, uint32 vendorPrice,
                uint32 currentBid=0, bool bidMax=false, uint64 willingPerItem=UINT32_MAX,
                bool prevent=true, float modifier=1) {
    Auction listing{buyout,currentBid,startbid}; auto auction = &listing;
    Item stack{count}; auto pItem = &stack;
    Prototype item{1}; auto prototype = &item;
    std::vector<uint32> vendorItemsPrices{UINT32_MAX, vendorPrice};
    float BuyingBotAcceptablePriceModifier = modifier;
    auto CalculateItemValue = [=](Prototype const*, uint64& bid, uint64& buyout) { bid = 0; buyout = willingPerItem; };
    for (int pass = 0; pass < 1; ++pass) {
    bool BuyingBotAlwaysBidMaxCalculatedPrice = bidMax;
    bool PreventOverpayingForVendorItems = prevent;
'''+source[start:end]+r'''
    if (doBid) {
        assert(calcBidAmount <= UINT32_MAX && calcBidAmount <= willingToPayForStackPrice);
        assert(!auction->bid || calcBidAmount >= uint64(auction->bid) + auction->GetAuctionOutBid());
    }
    return {doBuyout, doBid, preventedOverpayingForVendorItem, calcBidAmount};
    }
    return {false, false, false, 0};
}
int main() {
    assert(decide(20,240,0,12).buy);
    assert(decide(20,241,0,12).prevented);
    assert(decide(20,0,240,12).bid);
    assert(decide(20,0,241,12).prevented);
    assert(decide(20,UINT32_MAX,0,UINT32_MAX).buy);
    assert(decide(20,999,0,12,0,false,UINT32_MAX,false).buy);
    assert(decide(65536,UINT32_MAX,0,65536).buy);
    assert(decide(UINT32_MAX,UINT32_MAX,0,UINT32_MAX,0,false,UINT64_MAX).buy);
    assert(decide(2,1,0,UINT32_MAX,0,false,1ull << 63).buy);
    assert(decide(2,UINT32_MAX,0,UINT32_MAX,0,false,UINT64_MAX,true,1e30f).buy);
    assert(decide(2,99,0,UINT32_MAX,0,false,100,true,0.5f).buy);
    assert(!decide(2,100,0,UINT32_MAX,0,false,100,true,0.5f).buy);
    assert(!decide(20,100,0,UINT32_MAX,0,false,100,true,0).buy);
    assert(!decide(20,100,0,UINT32_MAX,0,false,100,true,-1).buy);
    assert(!decide(20,100,0,UINT32_MAX,0,false,100,true,std::numeric_limits<float>::infinity()).buy);
    assert(!decide(20,100,0,UINT32_MAX,0,false,100,true,std::numeric_limits<float>::quiet_NaN()).buy);
    auto capped = decide(20,0,1,UINT32_MAX,0,true);
    assert(capped.bid && capped.amount == UINT32_MAX);
    for (bool bidMax : {false, true}) {
        assert(!decide(1,0,100,UINT32_MAX,0,bidMax,99).bid);
        assert(decide(1,0,100,UINT32_MAX,0,bidMax,100).bid);
        assert(decide(1,0,100,UINT32_MAX,0,bidMax,101).bid);
        assert(!decide(1,100,100,UINT32_MAX,0,bidMax,99).buy);
        auto equal = decide(1,100,100,UINT32_MAX,0,bidMax,100);
        assert(!equal.buy && equal.bid);
        assert(decide(1,100,100,UINT32_MAX,0,bidMax,101).buy);
        auto exact = decide(2,0,0,UINT32_MAX,4090445039u,bidMax);
        assert(exact.bid && exact.amount == UINT32_MAX);
        assert(!decide(2,0,0,UINT32_MAX,4090445040u,bidMax).bid);
        assert(!decide(1,0,0,UINT32_MAX,100,bidMax,105).bid);
        assert(decide(1,0,0,UINT32_MAX,100,bidMax,106).bid);
    }
}
'''
work = project / 'work'
work.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='ahbot-buyer-', dir=work) as tmp:
    path = Path(tmp)
    (path / 'buyer.cpp').write_text(fixture)
    subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    str(path / 'buyer.cpp'), '-o', str(path / 'buyer')], check=True)
    subprocess.run([str(path / 'buyer')], check=True)
print('Buyer decision regression passed')
