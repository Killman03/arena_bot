from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class HealthMetric(Base):
    __tablename__ = "health_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(String, nullable=False)  # weight, steps, heart_rate, etc.
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)  # kg, steps, bpm, etc.
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="health_metrics")

    def __repr__(self):
        return f"<HealthMetric(id={self.id}, type='{self.metric_type}', value={self.value})>"


class HealthGoal(Base):
    __tablename__ = "health_goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    goal_type = Column(String, nullable=False)  # weight_loss, muscle_gain, etc.
    target_value = Column(Float, nullable=False)
    current_value = Column(Float, nullable=True)
    unit = Column(String, nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="health_goals")

    def __repr__(self):
        return f"<HealthGoal(id={self.id}, type='{self.goal_type}', target={self.target_value})>"


class HealthReminder(Base):
    __tablename__ = "health_reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reminder_type = Column(String, nullable=False)  # medication, exercise, checkup, etc.
    message = Column(Text, nullable=False)
    reminder_time = Column(DateTime(timezone=True), nullable=False)
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String, nullable=True)  # daily, weekly, monthly
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="health_reminders")

    def __repr__(self):
        return f"<HealthReminder(id={self.id}, type='{self.reminder_type}', time='{self.reminder_time}')>"


class GoogleFitToken(Base):
    __tablename__ = "google_fit_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="google_fit_token")

    def __repr__(self):
        return f"<GoogleFitToken(id={self.id}, user_id={self.user_id})>"
