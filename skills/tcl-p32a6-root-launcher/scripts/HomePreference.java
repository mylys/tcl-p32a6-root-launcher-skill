import android.content.ComponentName;
import android.content.IntentFilter;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/** Uses Android 5's package-manager API as root; no service or installed APK. */
public final class HomePreference {
  public static void main(String[] args) throws Exception {
    Object pm=Class.forName("android.app.AppGlobals").getMethod("getPackageManager").invoke(null);
    Class<?> iface=Class.forName("android.content.pm.IPackageManager");
    Method homes=iface.getMethod("getHomeActivities",List.class);
    ArrayList<ResolveInfo> candidates=new ArrayList<>();
    System.out.println("Preferred before: "+homes.invoke(pm,candidates));
    ComponentName[] set=new ComponentName[candidates.size()];
    ComponentName target=args.length==1?ComponentName.unflattenFromString(args[0]):null;
    int match=0; boolean found=false;
    for(int i=0;i<candidates.size();i++) {
      ResolveInfo r=candidates.get(i);
      set[i]=new ComponentName(r.activityInfo.packageName,r.activityInfo.name);
      System.out.println("Candidate: "+set[i]+" match="+r.match);
      if(set[i].equals(target)){found=true;match=r.match;}
    }
    if(args.length==0)return;
    if(!found)throw new IllegalArgumentException("Target is not a HOME candidate: "+target);
    IntentFilter filter=new IntentFilter(Intent.ACTION_MAIN);
    filter.addCategory(Intent.CATEGORY_HOME); filter.addCategory(Intent.CATEGORY_DEFAULT);
    iface.getMethod("replacePreferredActivity",IntentFilter.class,int.class,ComponentName[].class,ComponentName.class,int.class)
      .invoke(pm,filter,match,set,target,0);
    Object chosen=homes.invoke(pm,new ArrayList<ResolveInfo>());
    System.out.println("Preferred after: "+chosen);
    if(!target.equals(chosen))throw new IllegalStateException("Preferred HOME verification failed");
  }
}
