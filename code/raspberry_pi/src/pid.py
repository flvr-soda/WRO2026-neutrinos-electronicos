"""
Controlador PID genérico para lazo cerrado de velocidad.

El PID recibe la velocidad medida por odometría visual y calcula
la corrección de PWM que se envía al Arduino.
"""
import time


class PID:
    def __init__(self, kp=1.0, ki=0.0, kd=0.0, setpoint=0.0,
                 output_min=-100, output_max=100, integral_max=None):
        """
        Args:
            kp: Ganancia proporcional.
            ki: Ganancia integral.
            kd: Ganancia derivativa.
            setpoint: Valor objetivo inicial (cm/s).
            output_min: Salida mínima (PWM -100).
            output_max: Salida máxima (PWM 100).
            integral_max: Límite absoluto del término integral (anti-windup).
                          None = sin límite (no recomendado con ki > 0).
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.output_min = output_min
        self.output_max = output_max
        # Anti-windup: si no se especifica, usar output_max / ki como límite razonable
        if integral_max is not None:
            self.integral_max = integral_max
        elif ki > 0:
            self.integral_max = output_max / ki
        else:
            self.integral_max = float('inf')

        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time = None

    def set_setpoint(self, setpoint):
        """Actualiza el valor objetivo (velocidad deseada en cm/s)."""
        self.setpoint = setpoint

    def reset(self):
        """Reinicia el estado interno del PID."""
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time = None

    def compute(self, measured_value):
        """
        Calcula la salida del PID.

        Args:
            measured_value: Velocidad actual medida (cm/s).

        Returns:
            Salida del PID (valor de PWM entre output_min y output_max).
        """
        now = time.monotonic()
        if self._prev_time is None:
            self._prev_time = now
            # Primera iteración: arranque suave (el integral rampará la salida)
            return 0.0

        dt = now - self._prev_time
        if dt <= 0.0:
            return self._clamp(self.setpoint)

        error = self.setpoint - measured_value

        # Término proporcional
        p_term = self.kp * error

        # Término integral con anti-windup por clamp
        self._integral += error * dt
        self._integral = max(-self.integral_max, min(self.integral_max, self._integral))
        i_term = self.ki * self._integral

        # Término derivativo
        d_term = self.kd * (error - self._prev_error) / dt

        # Guardar estado
        self._prev_error = error
        self._prev_time = now

        output = p_term + i_term + d_term
        return self._clamp(output)

    def _clamp(self, value):
        """Restringe la salida entre los límites configurados."""
        return max(self.output_min, min(self.output_max, value))
