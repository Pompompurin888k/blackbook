# Blackbook Smart Recommendation Algorithm

## Overview
The recommendation system uses a **relevance scoring algorithm** instead of pure random selection to surface the most contextually appropriate providers to users.

## Scoring System

### Point Allocation

| Criteria | Points | Reasoning |
|----------|--------|-----------|
| Same Neighborhood | +10 | Highest relevance - same area preference |
| Same City (baseline) | +5 | Geographic proximity baseline |
| Same Build Type | +5 | Similar physical preferences |
| Recently Verified (< 30 days) | +3 | Quality signal - active verification |
| Currently Online | +2 | Immediate availability |
| Matching Services* | +2 per match | Service compatibility |

*Service matching planned for future implementation when profiles include services

## Implementation Details

### Query Flow
1. Fetch source provider's attributes (neighborhood, build, services)
2. Calculate relevance score for all eligible providers
3. Order by score DESC, then randomize ties
4. Return top N results (default: 4)

### Fallback Behavior
- If source provider not found → Simple random
- If database error → Online-first random
- Always excludes the source provider

## Main Listing Algorithm

### Provider Ordering Priority
1. **Online Status** - Live providers appear first
2. **Recent Verification** - Verified within 30 days prioritized
3. **Alphabetical** - Tie-breaker for consistent UX

### Benefits
- Increases engagement for newly verified providers
- Rewards active status toggling
- Maintains freshness of directory

## Performance Considerations

- Single query with computed columns (no joins)
- Indexed columns: `is_verified`, `is_active`, `city`, `neighborhood`
- Uses PostgreSQL's interval arithmetic for date calculations
- RANDOM() only applied as final tie-breaker

## Future Enhancements

### Planned Features
- [ ] Service matching weight (implement JSONB array overlap)
- [ ] User behavior tracking (view → contact rate)
- [ ] Time-of-day popularity scoring
- [ ] Distance-based scoring using coordinates
- [ ] Collaborative filtering (users who viewed X also viewed Y)

### Optimization Opportunities
- [ ] Pre-compute scores in materialized view
- [ ] Cache popular recommendations in Redis
- [ ] Add A/B testing for algorithm tuning

## Testing Scenarios

```sql
-- Test Case 1: Same neighborhood priority
SELECT * FROM providers WHERE neighborhood = 'Westlands' AND city = 'Nairobi';
-- Expected: Other Westlands providers ranked highest

-- Test Case 2: Build type matching
SELECT * FROM providers WHERE build = 'Slim' AND city = 'Nairobi';
-- Expected: Similar build providers prioritized

-- Test Case 3: Recent verification boost
SELECT * FROM providers WHERE created_at > NOW() - INTERVAL '30 days';
-- Expected: New providers boosted in rankings
```

## Version History

**v1.0** (2026-02-03)
- Initial smart recommendation algorithm
- Neighborhood, city, build, recency, online scoring
- Fallback to random on errors

**Planned v1.1**
- Service matching via JSONB array overlap
- Performance metrics logging
