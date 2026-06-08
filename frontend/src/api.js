import axios from 'axios'

const edgeApi = axios.create({ baseURL: '/api' })

export const fetchMetrics = (scope = 'recent_100') =>
  edgeApi.get('/metrics', { params: { scope } }).then(r => r.data)

export const fetchRecentTasks = (limit = 30) =>
  edgeApi.get('/tasks/recent', { params: { limit } }).then(r => r.data)

export const fetchDevices = () => edgeApi.get('/devices').then(r => r.data)

export const fetchAlerts = (limit = 15) =>
  edgeApi.get('/alerts', { params: { limit } }).then(r => r.data)

export const fetchScenario = () => edgeApi.get('/scenario').then(r => r.data)

export const fetchTopology = (scope = 'recent_100') =>
  edgeApi.get('/topology', { params: { scope } }).then(r => r.data)

export const setScenario = (name) =>
  edgeApi.post(`/scenario/${name}`).then(r => r.data)

export const setStrategy = (name) =>
  edgeApi.post(`/strategy/${name}`).then(r => r.data)

export const demoStart = () => edgeApi.post('/demo/start').then(r => r.data)
export const demoStop = () => edgeApi.post('/demo/stop').then(r => r.data)
export const demoTriggerSmoke = () => edgeApi.post('/demo/trigger_smoke').then(r => r.data)
export const demoScenarioTour = () => edgeApi.post('/demo/scenario_tour').then(r => r.data)
export const demoStatus = () => edgeApi.get('/demo/status').then(r => r.data)

export const fetchMlStatus = () => edgeApi.get('/ml/status').then(r => r.data)
export const fetchRlStatus = () => edgeApi.get('/rl/status').then(r => r.data)
export const fetchDigitalTwinStatus = () => edgeApi.get('/digital_twin/status').then(r => r.data)

export const DATA_SCOPES = [
  { id: 'all', label: 'Realtime All' },
  { id: 'recent_100', label: 'Recent 100 Tasks' },
  { id: 'recent_300', label: 'Recent 300 Tasks' },
  { id: 'latest_experiment', label: 'Latest Experiment' },
]

export const fetchAgentStatus = () => edgeApi.get('/agent/status').then(r => r.data)
export const fetchAgentExamples = () => edgeApi.get('/agent/examples').then(r => r.data)
export const fetchAgentToolsSchema = () => edgeApi.get('/agent/tools/schema').then(r => r.data)
export const submitAgentPlan = (body) => edgeApi.post('/agent/plan', body).then(r => r.data)
export const submitAgentIntent = (body) => edgeApi.post('/agent/intent', body).then(r => r.data)
