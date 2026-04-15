import Foundation

func formatTemperature(_ rawValue: Int?) -> String {
    guard let rawValue else { return "—" }
    return formatCelsius(Double(rawValue) / 100)
}

func formatCelsius(_ celsius: Double) -> String {
    String(format: "%.1f°C", quantizeHalfDegree(celsius))
}

func quantizeHalfDegree(_ celsius: Double) -> Double {
    (celsius * 2).rounded() / 2
}

func quantizeAirflow(_ airflow: Int) -> Int {
    max(0, min(100, Int((Double(airflow) / 5).rounded()) * 5))
}

func formattedTimestamp(_ date: Date?) -> String {
    guard let date else { return "Not yet refreshed" }
    return date.formatted(date: .omitted, time: .shortened)
}
