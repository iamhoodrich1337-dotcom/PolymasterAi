class PolymasterError(Exception): pass
class DataUnavailableError(PolymasterError): pass
class RiskLimitExceeded(PolymasterError): pass
class LiveModeLocked(PolymasterError): pass
class InsufficientLiquidity(PolymasterError): pass
