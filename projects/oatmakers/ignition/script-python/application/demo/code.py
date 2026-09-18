"""Customer demonstration services. All writes are confined to oat_demo."""
import time
from java.util import UUID
from java.lang import Exception as JavaException
from java.util.concurrent.locks import ReentrantLock

DATABASE = 'OatmakersDemo'
REVISION = 'showroom-4.3.1'
_cache = {}
_lock = ReentrantLock()


def _queryJson(sql, args=None):
	rows = system.db.runPrepQuery(sql, args or [], DATABASE)
	return system.util.jsonDecode(unicode(rows[0][0]))


def tick():
	try:
		_queryJson('SELECT oat_demo.tick_live()')
		_writeLiveTags(_queryJson('SELECT oat_demo.live_overview()'))
	except (Exception, JavaException) as exc:
		system.util.getLogger('Oatmakers.Demo').error('Demo continuity tick failed: {0}'.format(exc))


def health():
	try:
		result = _queryJson('SELECT oat_demo.health_live()')
		result['appRevision'] = REVISION
		return result
	except (Exception, JavaException):
		return {'ok': False, 'simulation': True, 'appRevision': REVISION,
			'message': 'Demo database unavailable. Inspect gateway connection OatmakersDemo.'}


def _empty(message):
	return {'ready': False, 'stale': True, 'simulated': True, 'message': message,
		'metrics': [], 'lines': [], 'trend': [], 'orders': [], 'planning': [], 'events': [],
		'losses': [], 'quality': [], 'batchOptions': [],
		'selectedBatch': {'reference': 'No batch available', 'product': '', 'quality': 'Awaiting data'},
		'inspection': {}, 'submissions': [], 'clock': '', 'window': '', 'health': {'ok': False, 'ageSeconds': 'n/a', 'coverageDays': 'n/a', 'lineCount': 'n/a', 'sampleCount': 'n/a'},
		'availability': 'n/a', 'performance': 'n/a', 'yield': 'n/a'}


def snapshot(scene='live', period='day', line=0, batch=''):
	key = (str(scene), str(period), int(line or 0), str(batch or ''))
	if key[0] not in ('live', 'stoppage', 'quality', 'recovery'):
		raise ValueError('Unknown scenario')
	if key[1] not in ('shift', 'day', 'week', 'month') or key[2] not in (0, 1, 2, 3):
		raise ValueError('Unknown filter')
	_lock.lock()
	try:
		now = time.time()
		cached = _cache.get(key)
		if cached and now-cached[0] < 8:
			return cached[1]
		try:
			result = _queryJson('SELECT oat_demo.snapshot(?, ?, ?, ?)', list(key))
			if not result.get('ready'):
				result = _empty(result.get('message', 'Preparing demonstration history.'))
			for line_data in result.get('lines', []):
				line_data['lineNumber'] = line_data.pop('id')
			result['orders'] = list(result.get('orders', []))
			result['submissions'] = recentOrders()
			result['appRevision'] = REVISION
		except (Exception, JavaException) as exc:
			system.util.getLogger('Oatmakers.Demo').warn('Demo snapshot unavailable: {0}'.format(exc))
			result = _empty('Demo data is temporarily unavailable. Check Demo health for connection status.')
		if len(_cache) > 128:
			_cache.clear()
		_cache[key] = (now, result)
		return result
	finally:
		_lock.unlock()


def recentOrders():
	return _queryJson("""SELECT coalesce(jsonb_agg(to_jsonb(x)), '[]') FROM (
		SELECT reference,product,quantity_kg,bags,mode,source,
		to_char(created_at AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI') AS submitted
		FROM oat_demo.operator_order ORDER BY created_at DESC LIMIT 100) x""")


def validateOrder(values):
	checks = {
		'reference': common.validation.input.validateTextInput(values.get('reference'), required=True),
		'product': common.validation.input.validateDropdownInput(values.get('product'), required=True,
			allowedValues=['Rolled oats', 'Steel-cut oats', 'Oat flour']),
		'quantity': common.validation.input.validateNumericInput(values.get('quantity'), negativeAllowed=False, decimalAllowed=True, required=True),
		'bags': common.validation.input.validateNumericInput(values.get('bags'), negativeAllowed=False, decimalAllowed=False, required=True),
		'mode': common.validation.input.validateDropdownInput(values.get('mode'), required=True, allowedValues=['Trial', 'Production', 'Hold'])
	}
	errors = dict((k, v['errorMessage']) for k, v in checks.items() if v['errorMessage'])
	clean = dict((k, v['validatedOutput']) for k, v in checks.items())
	if clean['reference'] and len(clean['reference']) > 40:
		errors['reference'] = 'Use at most 40 characters.'
	if clean['quantity'] is not None and not 0 < clean['quantity'] <= 100000:
		errors['quantity'] = 'Weight must be above 0 and at most 100,000 kg.'
	if clean['bags'] is not None and not 0 < clean['bags'] <= 10000:
		errors['bags'] = 'Bags must be between 1 and 10,000.'
	return {'valid': not bool(errors), 'errors': errors, 'values': clean,
		'message': 'Ready to create a demo batch.' if not errors else ' '.join(errors[k] for k in sorted(errors))}


def createOrder(values, requestId):
	validation = validateOrder(values)
	if not validation['valid']:
		raise ValueError(validation['message'])
	requestId = str(UUID.fromString(str(requestId)))
	v = validation['values']
	# The unique request ID makes repeat clicks and retried requests idempotent.
	result = _queryJson("""WITH inserted AS (
		INSERT INTO oat_demo.operator_order(request_id,reference,product,quantity_kg,bags,mode)
		SELECT CAST(? AS uuid),?,?,?,?,?
		WHERE (SELECT count(*) FROM oat_demo.operator_order WHERE created_at>now()-interval '1 minute')<60
		ON CONFLICT(request_id) DO NOTHING RETURNING reference
	) SELECT jsonb_build_object('created',EXISTS(SELECT 1 FROM inserted),
		'exists',EXISTS(SELECT 1 FROM oat_demo.operator_order WHERE request_id=CAST(? AS uuid) AND reference=? AND product=? AND quantity_kg=? AND bags=? AND mode=?))""",
		[requestId,v['reference'],v['product'],v['quantity'],v['bags'],v['mode'],requestId,v['reference'],v['product'],v['quantity'],v['bags'],v['mode']])
	if not result['created'] and not result['exists']:
		raise ValueError('Demo is busy. Try again in one minute.')
	_lock.lock()
	try:
		_cache.clear()
	finally:
		_lock.unlock()
	return 'Demo batch {0} created. It appears in the production requests list.'.format(v['reference'])


def recordInspection(reference):
	batch = batchDetails(reference)
	if not reference or not batch.get('available') or batch.get('status') == 'Scheduled':
		raise ValueError('Select a recorded production batch before recording its check.')
	saved = _queryJson("""WITH saved AS (
		INSERT INTO oat_demo.inspection(batch_reference,decision,peak_moisture,temperature)
		VALUES(?,?,?,?) ON CONFLICT(batch_reference) DO NOTHING RETURNING decision
	) SELECT jsonb_build_object('decision',coalesce((SELECT decision FROM saved),(SELECT decision FROM oat_demo.inspection WHERE batch_reference=?)))""",
		[str(reference), batch['quality'], batch['peak_moisture'], batch['temperature'],str(reference)])
	_lock.lock()
	try:
		_cache.clear()
	finally:
		_lock.unlock()
	return 'Demo inspection recorded for {0}: {1}.'.format(reference, saved['decision'])


def newRequestId():
	return str(UUID.randomUUID())

# Live SCADA and explicit range services for the Mustry UI screens.
TAG_ROOT = '[default]OatmakersDemo'
METRICS = {
	'rate': ('Throughput', 'Throughput', 'kg/h'),
	'temperature': ('Temperature', 'Temperature', u'\u00b0C'),
	'moisture': ('Moisture', 'Moisture', '%'),
	'pressure': ('Pressure', 'Pressure', 'bar'),
	'power': ('Power', 'Power', 'kW')
}


def _cachedQuery(key, ttl, sql, args):
	_lock.lock()
	try:
		now = time.time()
		cached = _cache.get(key)
		if cached and now-cached[0] < ttl:
			return cached[1]
		result = _queryJson(sql, args)
		if len(_cache) > 128:
			_cache.clear()
		_cache[key] = (now, result)
		return result
	finally:
		_lock.unlock()


def live(line=0):
	try:
		return _cachedQuery(('live5', int(line or 0)), 0.4, 'SELECT oat_demo.live_overview(?)', [int(line or 0)])
	except (Exception, JavaException):
		return {'ready': False, 'updatedEpochMs': 0, 'updatedAt': 'Unavailable',
			'lines': [], 'metrics': [], 'trend': [], 'shiftStart': ''}


def history(start, end, line=0, metric='rate'):
	if not start or not end or long(end) <= long(start):
		return {'points': [], 'count': 0, 'message': 'Choose a date and time range.'}
	if metric not in METRICS:
		raise ValueError('Unknown measurement')
	try:
		args = [long(start), long(end), int(line or 0), str(metric)]
		return _cachedQuery(('history4',)+tuple(args), 5, 'SELECT oat_demo.history_range(CAST(? AS bigint), CAST(? AS bigint), ?, ?)', args)
	except (Exception, JavaException) as exc:
		system.util.getLogger('Oatmakers.Demo').warn('History query failed: {0}'.format(exc))
		return {'points': [], 'count': 0, 'message': 'History unavailable. Choose a recorded range within 90 days.'}


def scadaSetpoint(line, metric):
	# These are the nominal operating targets used by the demonstration model.
	# Power is consumption, so it deliberately has no control setpoint.
	if metric == 'rate':
		return (32.0, 25.0, 21.0)[int(line)-1] * 60
	return {'temperature': 82.0, 'moisture': 11.4, 'pressure': 2.4}.get(metric)


def scadaTrend(line, metric):
	end = system.date.toMillis(system.date.now())
	result = history(end - 15*60*1000, end, int(line), metric)
	points = []
	setpoint = scadaSetpoint(line, metric)
	limits = {'temperature': (55.0, 86.0), 'moisture': (10.5, 13.0)}.get(metric, (None, None))
	for point in result.get('points', []):
		points.append({'ts': point['ts'], 'pv': point.get('line' + str(int(line))), 'sp': setpoint, 'low': limits[0], 'high': limits[1]})
	return {'points': points, 'message': result.get('message', '')}


def rangeSnapshot(start, end, line=0):
	if not start or not end or long(end) <= long(start):
		return _empty('Choose a date and time range.')
	try:
		return _cachedQuery(('range4',long(start),long(end),int(line or 0)), 5,
			'SELECT oat_demo.snapshot_range(CAST(? AS bigint), CAST(? AS bigint), ?)', [long(start),long(end),int(line or 0)])
	except (Exception, JavaException) as exc:
		system.util.getLogger('Oatmakers.Demo').warn('Range query failed: {0}'.format(exc))
		return _empty('Recorded data is unavailable for this range.')


def batches(start, end, line=0):
	if not start or not end or long(end) <= long(start):
		return []
	try:
		return _cachedQuery(('batches4',long(start),long(end),int(line or 0)), 5,
			'SELECT oat_demo.batches_range(CAST(? AS bigint), CAST(? AS bigint), ?)', [long(start),long(end),int(line or 0)])
	except (Exception, JavaException):
		return []


def timeline(start, end):
	if not start or not end or long(end) <= long(start):
		return []
	try:
		rows = _cachedQuery(('timeline5',long(start),long(end)), 5,
			'SELECT oat_demo.timeline_range(CAST(? AS bigint), CAST(? AS bigint), ?)', [long(start),long(end),0])
	except (Exception, JavaException):
		return []
	return [dict(row, id=row['reference'],
		description='{0} / {1}'.format(row['line'], row.get('status') or row.get('title')))
		for row in rows]


def batchDetails(reference):
	if not reference:
		return {'available': False, 'reference': '', 'message': 'Select a batch to inspect its measurements.'}
	try:
		return _cachedQuery(('batch4',str(reference)), 5, 'SELECT oat_demo.batch_detail(?)', [str(reference)])
	except (Exception, JavaException):
		return {'available': False, 'reference': str(reference), 'message': 'This batch is unavailable.'}


def showBatch(reference):
	if not str(reference).startswith('OM-'):
		return   # a stop or changeover bar carries no batch record
	system.perspective.openPopup('batch-details', 'Demo/BatchDetails',
		params={'reference': str(reference)}, title='Batch details',
		position={'width': 920, 'height': 400}, modal=False, draggable=True, resizable=True)


def showHistory(line, metric):
	line = int(line)
	if line not in (1,2,3) or metric not in METRICS:
		raise ValueError('Unknown demonstration tag')
	name, title, _unit = METRICS[metric]
	system.perspective.openPopup('history-{0}-{1}'.format(line,metric), 'Demo/TagHistory',
		params={'lineNumber': line, 'metric': metric, 'title': title,
			'tagPath': '{0}/Line{1}/{2}'.format(TAG_ROOT,line,name)},
		title='Line {0} / {1}'.format(line,title), position={'width': 980, 'height': 620},
		modal=False, draggable=True, resizable=True)


def _writeLiveTags(data):
	if not data.get('ready'):
		return
	if not system.tag.exists(TAG_ROOT+'/SchemaVersion'):
		folders = []
		for line in (1,2,3):
			tags = [{'name': values[0], 'tagType': 'AtomicTag', 'valueSource': 'memory', 'dataType': 'Float8', 'value': 0.0} for values in METRICS.values()]
			tags.extend([{'name': 'State', 'tagType': 'AtomicTag', 'valueSource': 'memory', 'dataType': 'String', 'value': 'Starting'},
				{'name': 'LastUpdate', 'tagType': 'AtomicTag', 'valueSource': 'memory', 'dataType': 'DateTime', 'value': system.date.fromMillis(0)}])
			folders.append({'name': 'Line{0}'.format(line), 'tagType': 'Folder', 'tags': tags})
		folders.append({'name': 'SchemaVersion', 'tagType': 'AtomicTag', 'valueSource': 'memory', 'dataType': 'String', 'value': '4'})
		qualities = system.tag.configure('[default]', [{'name':'OatmakersDemo','tagType':'Folder','tags':folders}], 'm')
		if any(not quality.isGood() for quality in qualities):
			raise ValueError('Could not initialize demo memory tags')
	paths, values = [], []
	for line in data['lines']:
		base = '{0}/Line{1}/'.format(TAG_ROOT,line['lineNumber'])
		for key, metadata in METRICS.items():
			paths.append(base+metadata[0]); values.append(float(line[key]))
		paths.extend([base+'State',base+'LastUpdate'])
		values.extend([line['state'],system.date.fromMillis(long(line['updatedEpochMs']))])
	qualities = system.tag.writeBlocking(paths, values)
	if any(not quality.isGood() for quality in qualities):
		raise ValueError('A demo tag write failed')


# The separator is a separate, deterministic process simulation for the reference HMI.
# It never writes plant tags or control setpoints.
def _separatorValue(signal, seconds):
	import math
	base, amplitude, period = {
		'pressure': (3.88, 0.025, 31.0), 'temperature': (25.95, 0.12, 67.0),
		'level': (47.33, 0.9, 43.0), 'interface': (21.51, 0.65, 59.0),
		'gas': (9.4, 0.07, 47.0), 'suction': (4.6, 0.04, 41.0),
		'discharge': (23.4, 0.09, 39.0), 'exportPressure': (23.1, 0.08, 37.0),
		'flow': (164.3, 1.3, 53.0), 'drain': (85.0, 0.15, 71.0), 'iop': (0.0, 0.0, 1.0)
	}.get(signal, (0.0, 0.0, 1.0))
	return base + amplitude * math.sin(seconds / period) + amplitude * 0.2 * math.sin(seconds / 3.1)


def separatorData():
	seconds = system.date.toMillis(system.date.now()) / 1000.0
	return dict((key, _separatorValue(key, seconds)) for key in
		('pressure', 'temperature', 'level', 'interface', 'gas', 'suction', 'discharge', 'exportPressure', 'flow', 'drain', 'iop'))


def _separatorSvg(content, width, height):
	import base64
	markup = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {0} {1}" preserveAspectRatio="none" width="{0}" height="{1}">{2}</svg>'.format(width, height, content)
	return 'data:image/svg+xml;base64,' + base64.b64encode(markup.encode('utf-8'))


def separatorVesselSvg():
	data = separatorData()
	level_y = 260.0 * (1 - data['level'] / 100.0)
	interface_y = 260.0 * (1 - data['interface'] / 100.0)
	body = '<defs><clipPath id="vessel"><rect x="2" y="2" width="606" height="256" rx="128"/></clipPath><linearGradient id="gas" x2="0" y2="1"><stop stop-color="#f4ecd4"/><stop offset="1" stop-color="#e6e6df"/></linearGradient></defs>'
	body += '<g clip-path="url(#vessel)"><rect width="610" height="260" fill="url(#gas)"/>'
	body += '<rect y="{0:.2f}" width="610" height="260" fill="#99a6b1"/>'.format(level_y)
	body += '<rect y="{0:.2f}" width="302" height="260" fill="#9dbccd"/>'.format(interface_y)
	body += '<path d="M303 {0:.2f} V259" stroke="#59605f" stroke-width="5"/></g>'.format(level_y)
	body += '<rect x="2" y="2" width="606" height="256" rx="128" fill="none" stroke="#616461" stroke-width="3"/>'
	for i, caption in enumerate(('10','7.5','5','2.5','0')):
		y = 13 + 29*i
		body += '<path d="M192 {0} h12" stroke="#d9ba66"/><text x="178" y="{1}" font-family="Arial" font-size="10" fill="#747873" text-anchor="end">{2}</text>'.format(y,y+3,caption)
	return _separatorSvg(body, 610, 260)


def separatorTrendSvg(signal, colour, setpoint):
	seconds = system.date.toMillis(system.date.now()) / 1000.0
	values = [_separatorValue(signal, seconds - 3600 + i*30) for i in range(121)]
	span = {'pressure': (0.0,10.0), 'level': (40.0,55.0), 'interface': (15.0,30.0)}.get(signal)
	if span is None:
		spread = max(max(values)-min(values), 1.0)
		span = (min(values)-spread, max(values)+spread)
	low, high = span
	points = [(3+i*274.0/120, 65-(value-low)/(high-low)*60) for i,value in enumerate(values)]
	body = ''
	if setpoint:
		y = 65-(float(setpoint)-low)/(high-low)*60
		body += '<path d="M3 {0:.2f} H277" stroke="#73c9d9" stroke-width="1" stroke-dasharray="4 4" fill="none"/>'.format(y)
	body += '<polyline points="{0}" stroke="{1}" stroke-width="1" fill="none"/>'.format(' '.join('{0:.2f},{1:.2f}'.format(x,y) for x,y in points), colour)
	body += '<circle cx="277" cy="{0:.2f}" r="2.2" fill="#df8074"/>'.format(points[-1][1])
	return _separatorSvg(body, 280, 70)


def separatorDetailValue(signal):
	if signal == 'iop':
		return 'IOP'
	units = {'pressure':'bar','temperature':u'\u00b0C','level':'%','interface':'%',
		'gas':'MMSCF/D','suction':'bar','discharge':'bar','exportPressure':'bar','flow':'M3/h','drain':'%'}
	return u'{0:.2f} {1}'.format(separatorData().get(signal, 0), units.get(signal, ''))


def showSeparatorDetail(tag, signal):
	system.perspective.openPopup('separator-detail', 'Demo/Separator/Detail',
		params={'tag':tag,'signal':signal}, title=tag,
		position={'width':520,'height':340}, modal=False, draggable=True, resizable=True)
