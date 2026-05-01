import AppKit
import ApplicationServices
import Foundation

/// 自动批准飞书任务（Accessibility）。
/// 仅在拨杆处于自动档时由 Agent 定时触发。
final class FeishuAutoApprover {
    private var lastApproveAt: Date = .distantPast
    private let minApproveInterval: TimeInterval = 1.2
    private let targetBundleKeywords = ["feishu", "lark"]
    private let targetNameKeywords = ["飞书", "feishu", "lark"]
    private let approveKeywords = ["批准", "同意", "通过", "approve", "agree", "ok", "确定"]
    private let skipKeywords = ["拒绝", "驳回", "取消", "reject", "deny", "cancel"]
    private let maxDepth = 7
    private let maxChildrenPerNode = 120

    /// - Returns: 成功点击了批准按钮时返回 true。
    func tickIfNeeded(autoMode: Bool, log: (String) -> Void) -> Bool {
        guard autoMode else { return false }
        guard Date().timeIntervalSince(lastApproveAt) >= minApproveInterval else { return false }
        guard AXIsProcessTrusted() else {
            log("飞书自动批准：辅助功能未授权（AXIsProcessTrusted=false）")
            return false
        }
        guard let appElement = focusedApplicationElement() else { return false }
        guard let pid = pid(of: appElement) else { return false }
        guard isFeishuApplication(pid: pid) else { return false }
        guard let root = focusedWindowOrAppRoot(of: appElement),
              let button = findApproveButton(in: root, depth: 0) else { return false }
        let ok = AXUIElementPerformAction(button, kAXPressAction as CFString) == .success
        if ok {
            lastApproveAt = Date()
            log("飞书自动批准：已点击批准按钮")
        }
        return ok
    }

    private func focusedApplicationElement() -> AXUIElement? {
        let system = AXUIElementCreateSystemWide()
        var value: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(system, kAXFocusedApplicationAttribute as CFString, &value)
        guard err == .success, let app = value else { return nil }
        return (app as! AXUIElement)
    }

    private func focusedWindowOrAppRoot(of app: AXUIElement) -> AXUIElement? {
        var value: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(app, kAXFocusedWindowAttribute as CFString, &value)
        if err == .success, let win = value {
            return (win as! AXUIElement)
        }
        return app
    }

    private func pid(of element: AXUIElement) -> pid_t? {
        var pid: pid_t = 0
        let err = AXUIElementGetPid(element, &pid)
        guard err == .success, pid > 0 else { return nil }
        return pid
    }

    private func isFeishuApplication(pid: pid_t) -> Bool {
        guard let app = NSRunningApplication(processIdentifier: pid) else { return false }
        let bundle = (app.bundleIdentifier ?? "").lowercased()
        let name = (app.localizedName ?? "").lowercased()
        if targetBundleKeywords.contains(where: { bundle.contains($0) }) { return true }
        if targetNameKeywords.contains(where: { name.contains($0.lowercased()) }) { return true }
        return false
    }

    private func findApproveButton(in root: AXUIElement, depth: Int) -> AXUIElement? {
        if depth > maxDepth { return nil }
        if isApproveButton(root) { return root }
        guard let children = children(of: root), !children.isEmpty else { return nil }
        for child in children.prefix(maxChildrenPerNode) {
            if let hit = findApproveButton(in: child, depth: depth + 1) {
                return hit
            }
        }
        return nil
    }

    private func children(of element: AXUIElement) -> [AXUIElement]? {
        var value: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &value)
        guard err == .success, let arr = value as? [Any] else { return nil }
        return arr.compactMap { $0 as? AXUIElement }
    }

    private func isApproveButton(_ element: AXUIElement) -> Bool {
        guard role(of: element) == (kAXButtonRole as String) else { return false }
        let content = [stringValue(of: element, attr: kAXTitleAttribute),
                       stringValue(of: element, attr: kAXDescriptionAttribute),
                       stringValue(of: element, attr: kAXValueAttribute)]
            .compactMap { $0 }
            .joined(separator: " ")
            .lowercased()
        guard !content.isEmpty else { return false }
        if skipKeywords.contains(where: { content.contains($0.lowercased()) }) { return false }
        return approveKeywords.contains(where: { content.contains($0.lowercased()) })
    }

    private func role(of element: AXUIElement) -> String? {
        stringValue(of: element, attr: kAXRoleAttribute)
    }

    private func stringValue(of element: AXUIElement, attr: CFString) -> String? {
        var value: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(element, attr, &value)
        guard err == .success, let raw = value else { return nil }
        if let s = raw as? String { return s }
        return String(describing: raw)
    }
}
