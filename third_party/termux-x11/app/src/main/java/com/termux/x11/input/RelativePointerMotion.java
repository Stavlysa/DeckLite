package com.termux.x11.input;

import android.view.MotionEvent;

/** Delivers captured relative samples without losing Android-batched movement. */
public final class RelativePointerMotion {
    private RelativePointerMotion() {}

    public interface Sink {
        void move(float x, float y);
    }

    public static void dispatch(MotionEvent event, boolean relativeAxes, int rotation,
                                float scale, Sink sink) {
        if (event.getActionMasked() != MotionEvent.ACTION_MOVE || event.getPointerCount() != 1)
            return;

        int axisX = relativeAxes ? MotionEvent.AXIS_RELATIVE_X : MotionEvent.AXIS_X;
        int axisY = relativeAxes ? MotionEvent.AXIS_RELATIVE_Y : MotionEvent.AXIS_Y;
        int history = event.getHistorySize();
        // Relative samples are NOT accumulated in getAxisValue(). Keep their order
        // rather than combining them: downstream pointer acceleration is nonlinear.
        for (int sample = 0; sample <= history; sample++) {
            float x = sample < history ? event.getHistoricalAxisValue(axisX, sample)
                                      : event.getAxisValue(axisX);
            float y = sample < history ? event.getHistoricalAxisValue(axisY, sample)
                                      : event.getAxisValue(axisY);
            float temporary;
            // Same rotation values as CapturedPointerTransformation. AUTO (-1)
            // stays unrotated for hardware mice; touchpad gestures resolve it separately.
            switch (rotation) {
                case 3: temporary = x; x = -y; y = temporary; break;
                case 1: temporary = x; x = y; y = -temporary; break;
                case 2: x = -x; y = -y; break;
                default: break;
            }
            sink.move(x * scale, y * scale);
        }
    }
}
