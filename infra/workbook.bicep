@description('Azure region for the workbook.')
param location string

@description('Resource ID of the Application Insights component the queries run against.')
param appInsightsId string

var summaryFilter = 'dependencies | where name == "cee.generate_summary"'
var airNowFilter = 'dependencies | where name == "cee.load_airnow"'

var workbookContent = {
  version: 'Notebook/1.0'
  items: [
    {
      type: 1
      name: 'title'
      content: {
        json: '## City Environment Explorer: AI and data telemetry\nCounts, timings and model metadata only. Prompts, evidence and model output are never recorded.'
      }
    }
    {
      type: 3
      name: 'summaries-per-day'
      content: {
        version: 'KqlItem/1.0'
        title: 'Summary calls per day'
        query: '${summaryFilter} | summarize Calls = count() by bin(timestamp, 1d), Outcome = tostring(customDimensions["cee.outcome"])'
        size: 1
        queryType: 0
        resourceType: 'microsoft.insights/components'
        visualization: 'barchart'
      }
    }
    {
      type: 3
      name: 'summary-latency'
      content: {
        version: 'KqlItem/1.0'
        title: 'Summary latency (ms), p50 and p95'
        query: '${summaryFilter} | summarize p50 = percentile(duration, 50), p95 = percentile(duration, 95) by bin(timestamp, 1h)'
        size: 1
        queryType: 0
        resourceType: 'microsoft.insights/components'
        visualization: 'timechart'
      }
    }
    {
      type: 3
      name: 'summary-tokens'
      content: {
        version: 'KqlItem/1.0'
        title: 'Tokens used per day'
        query: '${summaryFilter} | summarize InputTokens = sum(toint(customDimensions["gen_ai.usage.input_tokens"])), OutputTokens = sum(toint(customDimensions["gen_ai.usage.output_tokens"])) by bin(timestamp, 1d)'
        size: 1
        queryType: 0
        resourceType: 'microsoft.insights/components'
        visualization: 'barchart'
      }
    }
    {
      type: 3
      name: 'summary-failures'
      content: {
        version: 'KqlItem/1.0'
        title: 'Summary outcomes (citation rejections and model errors)'
        query: '${summaryFilter} | summarize Calls = count() by Outcome = tostring(customDimensions["cee.outcome"]), FinishReason = tostring(customDimensions["gen_ai.response.finish_reason"])'
        size: 1
        queryType: 0
        resourceType: 'microsoft.insights/components'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'airnow-load'
      content: {
        version: 'KqlItem/1.0'
        title: 'AirNow load time (ms) and rows'
        query: '${airNowFilter} | project timestamp, DurationMs = duration, Rows = toint(customDimensions["cee.daily_rows"]), Succeeded = success'
        size: 1
        queryType: 0
        resourceType: 'microsoft.insights/components'
        visualization: 'table'
      }
    }
  ]
}

resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: guid(appInsightsId, 'cee-telemetry-workbook')
  location: location
  kind: 'shared'
  properties: {
    displayName: 'City Environment Explorer telemetry'
    category: 'workbook'
    sourceId: appInsightsId
    serializedData: string(workbookContent)
  }
}
