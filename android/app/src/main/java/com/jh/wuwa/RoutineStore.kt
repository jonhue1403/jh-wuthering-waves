package com.jh.wuwa

import android.content.Context
import com.jh.wuwa.core.NormalizedPoint
import com.jh.wuwa.core.NormalizedRect
import com.jh.wuwa.core.TapRoutine
import com.jh.wuwa.core.VisualTemplate
import java.util.Base64
import org.json.JSONObject

/** Device-local calibration. Unknown formats are rejected instead of guessed. */
object RoutineStore {
    const val DEFAULT_TARGET = "com.kurogame.wutheringwaves.global"
    private const val PREFS = "mobile-prototype"

    fun target(context: Context): String = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        .getString("target", DEFAULT_TARGET) ?: DEFAULT_TARGET

    fun setTarget(context: Context, target: String) {
        require(target.length in 3..200 && target.matches(Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+"))) {
            "Enter an Android app package, for example $DEFAULT_TARGET"
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("target", target).apply()
    }

    fun save(context: Context, routine: TapRoutine) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString("routine", encode(routine)).apply()
    }

    fun load(context: Context): TapRoutine? {
        val value = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("routine", null) ?: return null
        return runCatching { decode(value) }.getOrNull()
    }

    fun clear(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove("routine").apply()
    }

    fun encode(routine: TapRoutine): String {
        val t = routine.template
        return JSONObject().apply {
            put("schema", 1)
            put("name", routine.name)
            put("targetPackage", routine.targetPackage)
            put("maxTaps", routine.maxTaps)
            put("timeoutMs", routine.timeoutMs)
            put("cooldownMs", routine.cooldownMs)
            put("matchThreshold", routine.matchThreshold)
            put("stableFrames", routine.stableFrames)
            put("tapX", routine.tap.x)
            put("tapY", routine.tap.y)
            put("template", JSONObject().apply {
                put("left", t.region.left); put("top", t.region.top)
                put("right", t.region.right); put("bottom", t.region.bottom)
                put("frameWidth", t.frameWidth); put("frameHeight", t.frameHeight)
                put("sampleSize", t.sampleSize)
                put("samples", Base64.getEncoder().encodeToString(t.samples))
            })
        }.toString()
    }

    fun decode(value: String): TapRoutine {
        require(value.length <= 16_384) { "Calibration is too large" }
        val json = JSONObject(value)
        exactInt(json, "schema", 1, 1)
        val t = json.getJSONObject("template")
        val size = exactInt(t, "sampleSize", 8, 64)
        val samples = Base64.getDecoder().decode(t.getString("samples"))
        require(samples.size == size * size) { "Incomplete calibration" }
        val template = VisualTemplate(
            NormalizedRect(unit(t, "left"), unit(t, "top"), unit(t, "right"), unit(t, "bottom")),
            exactInt(t, "frameWidth", 1, 8192), exactInt(t, "frameHeight", 1, 8192), samples, size)
        return TapRoutine(json.getString("name"), json.getString("targetPackage"), template,
            NormalizedPoint(unit(json, "tapX"), unit(json, "tapY")),
            exactInt(json, "maxTaps", 1, 50), exactInt(json, "timeoutMs", 1000, 300_000).toLong(),
            exactInt(json, "cooldownMs", 250, 60_000).toLong(),
            json.getDouble("matchThreshold"), exactInt(json, "stableFrames", 2, 10))
    }

    private fun exactInt(json: JSONObject, key: String, minimum: Int, maximum: Int): Int {
        val raw = json.get(key)
        require(raw is Number) { "$key must be an integer" }
        val number = raw.toDouble()
        require(number.isFinite() && number >= minimum && number <= maximum && number % 1.0 == 0.0) {
            "$key must be an integer between $minimum and $maximum"
        }
        return number.toInt()
    }

    private fun unit(json: JSONObject, key: String): Float {
        val raw = json.get(key)
        require(raw is Number) { "$key must be a number" }
        val value = raw.toDouble()
        require(value.isFinite() && value in 0.0..1.0) { "$key is outside the screen" }
        return value.toFloat()
    }
}
