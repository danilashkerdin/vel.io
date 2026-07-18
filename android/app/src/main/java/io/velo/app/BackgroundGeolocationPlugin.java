package io.velo.app;

import android.content.Intent;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "BackgroundGeolocation")
public class BackgroundGeolocationPlugin extends Plugin {

    private static BackgroundGeolocationPlugin instance;
    private static String lastJsCallback;

    public BackgroundGeolocationPlugin() {
        instance = this;
    }

    @PluginMethod
    public void start(PluginCall call) {
        Intent intent = new Intent(getActivity(), TrackingService.class);
        getActivity().startForegroundService(intent);
        call.resolve();
    }

    @PluginMethod
    public void stop(PluginCall call) {
        getActivity().stopService(new Intent(getActivity(), TrackingService.class));
        call.resolve();
    }

    public static void notifyListeners(String jsCode) {
        lastJsCallback = jsCode;
        if (instance != null && instance.getBridge() != null) {
            instance.getBridge().eval(jsCode, null);
        }
    }
}