"""Customer demonstration services. All writes are confined to oat_demo."""
import time
from java.util import UUID
from java.lang import Exception as JavaException
from java.util.concurrent.locks import ReentrantLock

DATABASE = 'OatmakersDemo'
REVISION = 'showroom-1'
_cache = {}
_lock = ReentrantLock()


def _queryJson(sql, args=None):
	rows = system.db.runPrepQuery(sql, args or [], DATABASE)
	return system.util.jsonDecode(str(rows[0][0]))


def tick():
	try:
		_queryJson('SELECT oat_demo.tick()')
	except (Exception, JavaException) as exc:
		system.util.getLogger('Oatmakers.Demo').error('Demo continuity tick failed: {0}'.format(exc))


def health():
	try:
		result = _queryJson('SELECT oat_demo.health()')
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
		FROM oat_demo.operator_order ORDER BY created_at DESC LIMIT 12) x""")


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
	return 'Demo batch {0} created. It appears in the recent submissions below.'.format(v['reference'])


def recordInspection(reference):
	data = _queryJson('SELECT oat_demo.snapshot(?, ?, ?, ?)', ['live', 'day', 0, str(reference)])
	batch = data.get('selectedBatch', {})
	if not reference or batch.get('reference') != reference:
		raise ValueError('Select a recent production batch before recording its check.')
	_queryJson("""WITH saved AS (
		INSERT INTO oat_demo.inspection(batch_reference,decision,peak_moisture,temperature)
		VALUES(?,?,?,?) ON CONFLICT(batch_reference) DO NOTHING RETURNING batch_reference
	) SELECT jsonb_build_object('saved', EXISTS(SELECT 1 FROM saved))""",
		[str(reference), batch['quality'], batch['peak_moisture'], batch['temperature']])
	_lock.lock()
	try:
		_cache.clear()
	finally:
		_lock.unlock()
	return 'Demo inspection recorded for {0}: {1}.'.format(reference, batch['quality'])
