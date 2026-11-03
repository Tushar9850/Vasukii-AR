package com.vasukii.ar;

import android.content.Intent;
import android.net.Uri;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * Opens Google's Scene Viewer (ARCore) with a public https .glb so the plant
 * is placed in the user's real surroundings through the camera.
 * Scene Viewer ships with the Google app; it prompts to install/update
 * "Google Play Services for AR" on first use.
 */
@CapacitorPlugin(name = "SceneViewer")
public class SceneViewerPlugin extends Plugin {

    @PluginMethod
    public void open(PluginCall call) {
        String file = call.getString("file");
        if (file == null || !file.startsWith("https://")) {
            call.reject("file must be a public https URL to a .glb");
            return;
        }
        String title = call.getString("title", "Vasukii plant");

        Uri uri = Uri.parse("https://arvr.google.com/scene-viewer/1.0").buildUpon()
                .appendQueryParameter("file", file)
                .appendQueryParameter("mode", "ar_preferred")
                .appendQueryParameter("title", title)
                .appendQueryParameter("resizable", "true")
                .build();

        JSObject ret = new JSObject();
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setData(uri);
        intent.setPackage("com.google.android.googlequicksearchbox");
        try {
            getActivity().startActivity(intent);
            ret.put("launched", true);
        } catch (Exception first) {
            // Fall back to any app that can handle the link (e.g. the browser).
            try {
                Intent generic = new Intent(Intent.ACTION_VIEW, uri);
                getActivity().startActivity(generic);
                ret.put("launched", true);
            } catch (Exception second) {
                ret.put("launched", false);
            }
        }
        call.resolve(ret);
    }
}
