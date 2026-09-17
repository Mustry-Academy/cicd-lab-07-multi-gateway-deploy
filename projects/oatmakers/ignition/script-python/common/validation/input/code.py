import re


try:
	_TEXT_TYPE = unicode
except NameError:
	_TEXT_TYPE = str


def _toText(value):
	if value is None:
		return u""
	return _TEXT_TYPE(value)


def _getNumericValidationError(normalizedText, negativeAllowed, decimalAllowed):
	if not negativeAllowed and normalizedText.startswith('-'):
		return u"Negative values are not allowed."
	if not decimalAllowed and '.' in normalizedText:
		return u"Enter a whole number."
	if decimalAllowed:
		return u"Enter a number."
	return u"Enter a whole number."


def validateNumericInput(value, negativeAllowed=True, decimalAllowed=False, required=False):
	"""
	Validate and normalize numeric text input.

	Args:
		value: Raw user input (string/number/None)
		negativeAllowed: Whether negative numbers are allowed
		decimalAllowed: Whether decimal numbers are allowed
		required: Whether an empty value is invalid

	Returns:
		Dict with:
			- errorMessage: unicode message or empty string
			- validatedOutput: int/float/None

	Examples:
		validateNumericInput("1,5", decimalAllowed=True)
		# -> {"errorMessage": u"", "validatedOutput": 1.5}
	"""
	text = _toText(value).strip()
	result = {
		"errorMessage": u"",
		"validatedOutput": None
	}

	if len(text) == 0:
		if required:
			result["errorMessage"] = u"Required."
		return result

	normalizedText = text.replace(',', '.')
	if decimalAllowed:
		pattern = r'^-?[0-9]+(?:\.[0-9]+)?$' if negativeAllowed else r'^[0-9]+(?:\.[0-9]+)?$'
	else:
		pattern = r'^-?[0-9]+$' if negativeAllowed else r'^[0-9]+$'

	if re.match(pattern, normalizedText) is None:
		result["errorMessage"] = _getNumericValidationError(normalizedText, negativeAllowed, decimalAllowed)
		return result

	if decimalAllowed and '.' in normalizedText:
		result["validatedOutput"] = float(normalizedText)
	else:
		result["validatedOutput"] = int(normalizedText)

	return result

def validateTextInput(value, required=False):
	"""
	Validate and normalize text input.

	Args:
		value: Raw user input (string/number/None)
		required: Whether a null or empty value is invalid

	Returns:
		Dict with:
			- errorMessage: unicode message or empty string
			- validatedOutput: unicode/None

	Examples:
		validateTextInput("abc")
		# -> {"errorMessage": u"", "validatedOutput": u"abc"}
	"""
	result = {
		"errorMessage": u"",
		"validatedOutput": None
	}

	text = _toText(value).strip()

	if value is None:
		if required:
			result["errorMessage"] = u"Required."
		return result

	if required and len(text) == 0:
		result["errorMessage"] = u"Required."
		return result

	result["validatedOutput"] = text
	return result


def resolveValidatedInput(value, currentValue, validationResult, blankValue=None):
	"""
	Resolve the final value to save from a raw input and a validation result.

	Args:
		value: Raw user input (string/number/None)
		currentValue: Existing value to keep when the input is invalid
		validationResult: Result returned by validateNumericInput / validateTextInput
		blankValue: Value to use when the input is blank

	Returns:
		The blank value, the current value, or the validated output.
	"""
	text = _toText(value).strip()
	if len(text) == 0:
		return blankValue

	if len(_toText(validationResult.get("errorMessage", u""))) > 0:
		return currentValue

	return validationResult.get("validatedOutput", currentValue)


def validateDropdownInput(value, required=False, allowedValues=None):
	"""
	Validate dropdown/select input.

	Args:
		value: Selected value (can be int, str, None)
		required: Whether a null/empty value is invalid
		allowedValues: Optional list of allowed values to validate against

	Returns:
		Dict with:
			- errorMessage: unicode message or empty string
			- validatedOutput: The value if valid, None otherwise

	Examples:
		validateDropdownInput(5, required=True)
		# -> {"errorMessage": u"", "validatedOutput": 5}

		validateDropdownInput(None, required=True)
		# -> {"errorMessage": u"Required.", "validatedOutput": None}

		validateDropdownInput(99, allowedValues=[1, 2, 5])
		# -> {"errorMessage": u"Choose a valid option.", "validatedOutput": None}
	"""
	result = {
		"errorMessage": u"",
		"validatedOutput": None
	}

	if value is None:
		if required:
			result["errorMessage"] = u"Required."
		return result

	if allowedValues is not None and value not in allowedValues:
		result["errorMessage"] = u"Choose a valid option."
		return result

	result["validatedOutput"] = value
	return result
