#!/usr/bin/env python3
"""Pull GA4 reports for Xerus marketing standup.

Usage:
    python ga4_report.py                    # Last 7 days overview
    python ga4_report.py --days 30          # Last 30 days
    python ga4_report.py --realtime         # Real-time active users
    python ga4_report.py --conversions      # Conversion events
    python ga4_report.py --utm              # UTM campaign breakdown
    python ga4_report.py --full             # Everything

Environment:
    GOOGLE_APPLICATION_CREDENTIALS  Path to service account JSON
    GA4_PROPERTY_ID                 GA4 property ID (default: 497430961)
"""
import argparse
import os
import sys
from pathlib import Path

# Load .env from workspace root
env_path = Path(__file__).resolve().parents[4] / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

# Default credentials path
if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
    # Try common locations
    for candidate in [
        Path(__file__).resolve().parents[5] / 'glass/xerus_backend/xerus-d067d-firebase-adminsdk-fbsvc-cda42875c5.json',
    ]:
        if candidate.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(candidate)
            break

PROPERTY_ID = os.environ.get('GA4_PROPERTY_ID', '497430961')

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, RunRealtimeReportRequest,
    DateRange, Dimension, Metric, FilterExpression, Filter
)

client = BetaAnalyticsDataClient()


def report_overview(days=7):
    """Traffic overview for last N days."""
    request = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        date_ranges=[DateRange(start_date=f'{days}daysAgo', end_date='today')],
        metrics=[
            Metric(name='activeUsers'),
            Metric(name='sessions'),
            Metric(name='screenPageViews'),
            Metric(name='newUsers'),
            Metric(name='engagementRate'),
            Metric(name='averageSessionDuration'),
        ],
    )
    response = client.run_report(request)
    print(f'=== OVERVIEW (last {days} days) ===')
    for row in response.rows:
        eng_rate = float(row.metric_values[4].value) * 100
        avg_duration = float(row.metric_values[5].value)
        print(f'Active Users:     {row.metric_values[0].value}')
        print(f'Sessions:         {row.metric_values[1].value}')
        print(f'Page Views:       {row.metric_values[2].value}')
        print(f'New Users:        {row.metric_values[3].value}')
        print(f'Engagement Rate:  {eng_rate:.1f}%')
        print(f'Avg Session:      {avg_duration:.0f}s')


def report_traffic(days=7):
    """Traffic sources breakdown."""
    request = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        date_ranges=[DateRange(start_date=f'{days}daysAgo', end_date='today')],
        dimensions=[Dimension(name='sessionSource'), Dimension(name='sessionMedium')],
        metrics=[Metric(name='sessions'), Metric(name='activeUsers')],
    )
    response = client.run_report(request)
    print(f'\n=== TRAFFIC SOURCES (last {days} days) ===')
    for row in response.rows:
        source = row.dimension_values[0].value
        medium = row.dimension_values[1].value
        sessions = row.metric_values[0].value
        users = row.metric_values[1].value
        print(f'  {source} / {medium}: {sessions} sessions, {users} users')


def report_utm(days=7):
    """UTM campaign breakdown — tracks which Twitter strategy drives traffic."""
    print(f'\n=== UTM CAMPAIGNS (last {days} days) ===')
    request = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        date_ranges=[DateRange(start_date=f'{days}daysAgo', end_date='today')],
        dimensions=[
            Dimension(name='sessionCampaignName'),
            Dimension(name='sessionMedium'),
            Dimension(name='sessionSource'),
        ],
        metrics=[Metric(name='sessions'), Metric(name='activeUsers')],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name='sessionSource',
                string_filter=Filter.StringFilter(
                    value='twitter',
                    match_type=Filter.StringFilter.MatchType.EXACT,
                ),
            )
        ),
    )
    response = client.run_report(request)
    if not response.rows:
        print('  No Twitter UTM traffic yet. Agents need to start posting with UTM links.')
        return
    for row in response.rows:
        campaign = row.dimension_values[0].value
        medium = row.dimension_values[1].value
        sessions = row.metric_values[0].value
        users = row.metric_values[1].value
        print(f'  campaign={campaign}, medium={medium}: {sessions} sessions, {users} users')


def report_conversions(days=7):
    """Conversion events — early access form submissions."""
    print(f'\n=== CONVERSIONS (last {days} days) ===')
    for event_name in ['generate_lead', 'early_access_requested']:
        request = RunReportRequest(
            property=f'properties/{PROPERTY_ID}',
            date_ranges=[DateRange(start_date=f'{days}daysAgo', end_date='today')],
            dimensions=[Dimension(name='eventName')],
            metrics=[Metric(name='eventCount')],
            dimension_filter=FilterExpression(
                filter=Filter(
                    field_name='eventName',
                    string_filter=Filter.StringFilter(
                        value=event_name,
                        match_type=Filter.StringFilter.MatchType.EXACT,
                    ),
                )
            ),
        )
        response = client.run_report(request)
        if response.rows:
            count = response.rows[0].metric_values[0].value
            print(f'  {event_name}: {count}')
        else:
            print(f'  {event_name}: 0')


def report_realtime():
    """Real-time active users."""
    print('\n=== REAL-TIME ===')
    request = RunRealtimeReportRequest(
        property=f'properties/{PROPERTY_ID}',
        metrics=[Metric(name='activeUsers')],
        dimensions=[Dimension(name='unifiedScreenName')],
    )
    response = client.run_realtime_report(request)
    total = 0
    for row in response.rows:
        page = row.dimension_values[0].value
        users = int(row.metric_values[0].value)
        total += users
        print(f'  {page}: {users} active')
    if total == 0:
        print('  No active users right now')
    else:
        print(f'  TOTAL: {total} active users')


def report_pages(days=7):
    """Top pages."""
    request = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        date_ranges=[DateRange(start_date=f'{days}daysAgo', end_date='today')],
        dimensions=[Dimension(name='pagePath')],
        metrics=[Metric(name='screenPageViews'), Metric(name='activeUsers')],
    )
    response = client.run_report(request)
    print(f'\n=== TOP PAGES (last {days} days) ===')
    for row in response.rows:
        page = row.dimension_values[0].value
        views = row.metric_values[0].value
        users = row.metric_values[1].value
        print(f'  {page}: {views} views, {users} users')


def report_countries(days=7):
    """Top countries."""
    request = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        date_ranges=[DateRange(start_date=f'{days}daysAgo', end_date='today')],
        dimensions=[Dimension(name='country')],
        metrics=[Metric(name='activeUsers')],
        limit=10,
    )
    response = client.run_report(request)
    print(f'\n=== TOP 10 COUNTRIES (last {days} days) ===')
    for row in response.rows:
        country = row.dimension_values[0].value
        users = row.metric_values[0].value
        print(f'  {country}: {users} users')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GA4 report for Xerus marketing standup')
    parser.add_argument('--days', type=int, default=7, help='Number of days (default: 7)')
    parser.add_argument('--realtime', action='store_true', help='Show real-time active users')
    parser.add_argument('--conversions', action='store_true', help='Show conversion events')
    parser.add_argument('--utm', action='store_true', help='Show UTM campaign breakdown')
    parser.add_argument('--full', action='store_true', help='Show everything')
    args = parser.parse_args()

    if args.realtime:
        report_realtime()
    elif args.conversions:
        report_conversions(args.days)
    elif args.utm:
        report_utm(args.days)
    elif args.full:
        report_overview(args.days)
        report_traffic(args.days)
        report_utm(args.days)
        report_conversions(args.days)
        report_pages(args.days)
        report_countries(args.days)
        report_realtime()
    else:
        report_overview(args.days)
        report_traffic(args.days)
